#!/usr/bin/env python3
"""Run a loopback-only RC Pi smoke test, recording latency and resource samples."""
import argparse
import base64
import json
import platform
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def proc_values(path, keys):
    rows = Path(path).read_text().splitlines()
    fields = {parts[0].rstrip(":"): int(parts[1]) for line in rows if (parts := line.split())
              and parts[0].rstrip(":") in keys}
    return {key: fields.get(key) for key in keys}


def text_file(path):
    try:
        return Path(path).read_text().strip().rstrip("\0")
    except OSError:
        return None


def throttled():
    try:
        return subprocess.check_output(["vcgencmd", "get_throttled"], text=True, timeout=3).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def process_children(pid):
    children = set()
    queue = [pid]
    while queue:
        root = Path("/proc") / str(queue.pop()) / "task"
        for file in root.glob("*/children"):
            for child in (text_file(file) or "").split():
                child = int(child)
                if child not in children:
                    children.add(child)
                    queue.append(child)
    return children


def sample(pid):
    mem = proc_values("/proc/meminfo", {"MemAvailable", "SwapTotal", "SwapFree"})
    pids = process_children(pid)
    rss = {}
    for process in pids | {pid}:
        try:
            path = Path("/proc") / str(process)
            value = proc_values(path / "status", {"VmRSS"})["VmRSS"]
            name = text_file(path / "comm")
            if value is not None and name:
                rss[process] = {"name": name, "rss_kib": value}
        except OSError:
            continue
    temp = text_file("/sys/class/thermal/thermal_zone0/temp")
    return {
        "mem_available_kib": mem["MemAvailable"],
        "swap_used_kib": mem["SwapTotal"] - mem["SwapFree"],
        "temperature_c": int(temp) / 1000 if temp else None,
        "load_average": text_file("/proc/loadavg"),
        "owned_process_rss": rss,
    }


def request(base, endpoint, payload=None, timeout=130):
    data = None if payload is None else json.dumps(payload).encode()
    with urlopen(Request(base + endpoint, data, {"Content-Type": "application/json"}), timeout=timeout) as response:
        return json.load(response)


def wait_for(callback, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = callback()
        if value is not None:
            return value
        time.sleep(.15)
    raise TimeoutError("Pi probe timed out")


def inspect(base, image, source):
    started = time.monotonic()
    record = request(base, "/api/inspect", {
        "image": "data:image/jpeg;base64," + base64.b64encode(image.read_bytes()).decode(),
        "source": source, "pill_present_confirmed": True,
    })
    return record, round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("vision-dir", "llama-runner", "tokenizer", "normal", "defective", "run-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--port", type=int, default=18775)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expect-loopback-only", action="store_true")
    args = parser.parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=False)
    database_dir = args.run_dir / "database"
    base = f"http://127.0.0.1:{args.port}"
    monitor_stop = threading.Event()
    counters = {"oom_kill", "pswpin", "pswpout"}
    report = {
        "revision": args.revision, "machine": platform.machine(),
        "device_model": text_file("/proc/device-tree/model"),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "throttled_before": throttled(), "vmstat_before": proc_values("/proc/vmstat", counters),
        "cases": [], "status": "incomplete",
    }
    samples = []
    started = time.monotonic()
    with (args.run_dir / "service.log").open("w") as log:
        server = subprocess.Popen([
            sys.executable, str(ROOT / "app/app.py"), "--vision-dir", args.vision_dir,
            "--llama-runner", args.llama_runner, "--tokenizer", args.tokenizer,
            "--data-dir", database_dir, "--port", str(args.port),
        ], stdout=log, stderr=subprocess.STDOUT)

        def monitor():
            while not monitor_stop.is_set():
                samples.append({"since_start_s": round(time.monotonic() - started, 3), **sample(server.pid)})
                monitor_stop.wait(.2)

        sampler = threading.Thread(target=monitor)
        sampler.start()

        def ready():
            if server.poll() is not None:
                raise RuntimeError("Pi service terminated during startup")
            try:
                return request(base, "/api/system", timeout=2)
            except URLError:
                return None

        def finished(inspection_id):
            record = request(base, "/api/inspection/" + inspection_id)
            return record if record["llama_status"] != "PENDING" else None

        def record_case(label, expected, initial, seconds):
            result = wait_for(lambda: finished(initial["inspection_id"]), 200)
            keys = ("screening_decision", "required_action", "severity", "dispensing_authorized", "verdict_wall_s")
            assert all(result[key] == initial[key] for key in keys)
            assert result["screening_decision"] == expected
            assert result["required_action"] == ("QUARANTINE" if expected == "FAIL" else "STANDARD_QC_REVIEW")
            assert result["severity"] == "NOT_ASSESSED" and result["dispensing_authorized"] is False
            assert result["llama_status"] in {"COMPLETED", "FALLBACK"}
            assert expected != "FAIL" or result["advisory_check_id"] != 1
            report["cases"].append({"case": label, "http_verdict_s": seconds, "record": result})

        try:
            report["system"] = wait_for(ready, 12)
            report["server_ready_s"] = round(time.monotonic() - started, 3)
            report["network_interfaces"] = sorted(name for _, name in socket.if_nameindex())
            if args.expect_loopback_only:
                assert report["network_interfaces"] == ["lo"]
                assert report["system"]["network_up"] is False
            cold, latency = inspect(base, args.normal, "upload")
            record_case("first after service startup", "PASS", cold, latency)
            warm, warm_latency = inspect(base, args.defective, "upload")
            # Ensure the advisory native process is running before admitting the next verdict.
            wait_for(lambda: next((info for info in sample(server.pid)["owned_process_rss"].values()
                                   if info["name"] == args.llama_runner.name), None), 10)
            with ThreadPoolExecutor(max_workers=1) as clients:
                next_request = clients.submit(inspect, base, args.normal, "video_frame")
                record_case("warm, inference idle at submission", "FAIL", warm, warm_latency)
                overlapping, busy_latency = next_request.result(timeout=135)
            record_case("submitted while Llama was active", "PASS", overlapping, busy_latency)
            exported = request(base, "/api/export")
            assert len(exported) == len(report["cases"])
            assert {row["inspection_id"] for row in exported} == {
                case["record"]["inspection_id"] for case in report["cases"]}
            report["status"] = "passed"
        finally:
            if server.poll() is None:
                server.terminate()
            report["service_return_code"] = server.wait(timeout=110)
            report["remaining_owned_processes"] = sorted({
                pid for item in samples for pid in item["owned_process_rss"]
                if pid != server.pid and Path("/proc").joinpath(str(pid)).exists()
            })
            monitor_stop.set()
            sampler.join()
            report["throttled_after"] = throttled()
            report["vmstat_after"] = proc_values("/proc/vmstat", counters)
            report["samples"] = samples
            (args.run_dir / "hardware.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"run_dir": str(args.run_dir), "status": report["status"],
                      "service_return_code": report["service_return_code"]}))


if __name__ == "__main__":
    main()
