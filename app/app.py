#!/usr/bin/env python3
"""Serve the offline PillGuard UI and its local SQLite inspection history."""
import argparse
import base64
import binascii
import json
import fcntl
import signal
import logging
import os
import platform
import queue
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image, UnidentifiedImageError

from pipeline import Pipeline, advisory_fields

HTML = Path(__file__).with_name("index.html").read_bytes()
MAX_BODY = 18 * 1024 * 1024
MAX_IMAGE = 12 * 1024 * 1024
MAX_PIXELS = 16_000_000
ADVISORY_CAPACITY = 2
ADVISORY_KEYS = advisory_fields("FAIL", 0, "ERROR").keys()


def decode_request(payload):
    if not isinstance(payload, dict) or payload.get("pill_present_confirmed") is not True:
        raise ValueError("Confirm that a tablet is visible before inspection.")
    shift_note = payload.get("shift_note", "")
    if not isinstance(shift_note, str) or len(shift_note) > 160:
        raise ValueError("Shift note must be text no longer than 160 characters.")
    source = payload.get("source")
    if source not in ("upload", "camera", "video_frame"):
        raise ValueError("Invalid image source.")
    data_url = payload.get("image")
    if not isinstance(data_url, str):
        raise ValueError("Select a JPEG or PNG image.")
    header, _, encoded = data_url.partition(",")
    formats = {"data:image/jpeg;base64": ("JPEG", ".jpg"), "data:image/png;base64": ("PNG", ".png")}
    if header not in formats:
        raise ValueError("Select a JPEG or PNG image.")
    image_format, suffix = formats[header]
    try:
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > MAX_IMAGE:
            raise ValueError("Image must be between 1 byte and 12 MiB.")
        with Image.open(BytesIO(data), formats=[image_format]) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError("Image exceeds 16 megapixels.")
            image.verify()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Cannot read the selected JPEG or PNG.") from exc
    return data, source, suffix, shift_note


def make_handler(engine, database, *, start=True):
    advisory_queue = queue.Queue(maxsize=ADVISORY_CAPACITY)
    advisory_slots = threading.BoundedSemaphore(ADVISORY_CAPACITY)
    inspection_slot = threading.BoundedSemaphore(1)
    stopping = threading.Event()
    storage_failed = threading.Event()

    def recover_pending():
        with closing(sqlite3.connect(database)) as db, db:
            rows = db.execute(
                "SELECT id, record_json FROM inspections WHERE json_extract(record_json, '$.llama_status') = 'PENDING'"
            ).fetchall()
            for inspection_id, raw in rows:
                record = json.loads(raw)
                record.update(advisory_fields(record["screening_decision"], 0, "ERROR",
                                              diagnostic="Interrupted before advisory completion"))
                db.execute("UPDATE inspections SET record_json = ? WHERE id = ?",
                           (json.dumps(record, allow_nan=False), inspection_id))

    def save_advisory(record, inspection_id):
        encoded = json.dumps(record, allow_nan=False)
        for attempt in range(3):
            try:
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute("UPDATE inspections SET record_json = ? WHERE id = ?",
                               (encoded, inspection_id))
                return
            except sqlite3.OperationalError:
                if attempt == 2:
                    raise
                time.sleep(.1)

    def update_advisory(inspection_id, queued_at):
        with closing(sqlite3.connect(database)) as db:
            row = db.execute("SELECT created_at, record_json FROM inspections WHERE id = ?",
                             (inspection_id,)).fetchone()
            if not row:
                return
            created_at, raw_record = row
            history = db.execute(
                "SELECT record_json FROM inspections WHERE created_at < ? ORDER BY created_at DESC, id DESC LIMIT 10",
                (created_at,),
            ).fetchall()
        record = json.loads(raw_record)
        if record["llama_status"] != "PENDING":
            return
        decisions = [json.loads(item[0]).get("screening_decision") for item in history]
        last10 = decisions.count("FAIL")
        last3 = decisions[:3].count("FAIL")
        decision = record["screening_decision"]
        queue_delay = time.monotonic() - queued_at
        try:
            if stopping.is_set() or storage_failed.is_set():
                fields = advisory_fields(decision, last10, "ERROR", diagnostic="Service stopped before advisory")
            else:
                fields = engine.advisory(decision, record["probability_defective"], last10, last3,
                                         record.get("shift_note", ""))
            # Advisory workers may only write fields in their own contract.
            updates = {key: fields[key] for key in ADVISORY_KEYS}
            json.dumps(updates, allow_nan=False)
        except Exception:
            logging.exception("Advisory computation failed for %s", inspection_id)
            updates = advisory_fields(decision, last10, "ERROR", diagnostic="Advisory worker exception")
            fields = {}
        record.update(updates)
        record.update(recent_last10_fails=last10, recent_last3_fails=last3,
                      llama_queue_s=round(queue_delay + fields.get("llama_lock_wait_s", 0), 3))
        save_advisory(record, inspection_id)

    def worker():
        while True:
            job = advisory_queue.get()
            try:
                if job is None:
                    return
                update_advisory(*job)
            except Exception:
                storage_failed.set()
                logging.exception("Advisory store unavailable for %s", job[0])
            finally:
                if job is not None:
                    advisory_slots.release()
                advisory_queue.task_done()

    recovery_complete = False
    thread = threading.Thread(target=worker, name="pillguard-llama-worker", daemon=True)

    def system_info():
        def read_text(path):
            try:
                return Path(path).read_text().strip().replace("\x00", "") or None
            except (OSError, ValueError):
                return None
        def meminfo_kb(key):
            try:
                for line in Path("/proc/meminfo").read_text().splitlines():
                    if line.startswith(key + ":"):
                        return int(line.split()[1]) * 1024
            except (OSError, ValueError, IndexError):
                pass
            return None
        try:
            temperature = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000
        except (OSError, ValueError):
            temperature = None
        try:
            uptime = float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            uptime = None
        interfaces = []
        try:
            for item in Path("/sys/class/net").iterdir():
                if item.name != "lo" and (item / "operstate").read_text().strip() == "up":
                    interfaces.append(item.name)
        except OSError:
            pass
        return {"device_model": read_text("/proc/device-tree/model"),
                "cpu_architecture": platform.machine() or None,
                "core_count": os.cpu_count(), "total_ram_bytes": meminfo_kb("MemTotal"),
                "available_ram_bytes": meminfo_kb("MemAvailable"), "soc_temperature_c": temperature,
                "uptime_s": uptime, "network_up": bool(interfaces) if Path("/sys/class/net").exists() else None}
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload, content_type="application/json; charset=utf-8", download=False):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="pillguard_inspection_history.json"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self.reply(200, HTML, "text/html; charset=utf-8")
                return
            if self.path == "/api/system":
                self.reply(200, system_info())
                return
            request = urlsplit(self.path)
            if request.path == "/api/stats":
                params = parse_qs(request.query)
                try:
                    start, end = (datetime.fromisoformat(params[key][0]) for key in ("start", "end"))
                    if (start.tzinfo is None or end.tzinfo is None
                            or not 0 < (end - start).total_seconds() <= 26 * 3600):
                        raise ValueError
                except (KeyError, ValueError, OverflowError):
                    self.reply(400, {"error": "Supply a valid daily statistics range."})
                    return
                bounds = [date.astimezone(timezone.utc).isoformat(timespec="microseconds") for date in (start, end)]
                with closing(sqlite3.connect(database)) as db:
                    rows = db.execute(
                        "SELECT json_extract(record_json, '$.screening_decision'), count(*) "
                        "FROM inspections WHERE created_at >= ? AND created_at < ? GROUP BY 1", bounds,
                    ).fetchall()
                counts = dict(rows)
                self.reply(200, {"passed": counts.get("PASS", 0), "failed": counts.get("FAIL", 0)})
                return
            if self.path.startswith("/api/inspection/"):
                inspection_id = self.path.rsplit("/", 1)[-1]
                with closing(sqlite3.connect(database)) as db:
                    row = db.execute("SELECT record_json FROM inspections WHERE id = ?", (inspection_id,)).fetchone()
                if row:
                    record = json.loads(row[0])
                    if storage_failed.is_set() and record.get("llama_status") == "PENDING":
                        record.update(advisory_fields(record["screening_decision"], 0, "ERROR",
                                                      diagnostic="Advisory storage unavailable; restart required"))
                    self.reply(200, record)
                else:
                    self.reply(404, {"error": "Inspection not found"})
                return
            if self.path not in ("/api/history", "/api/export"):
                self.reply(404, {"error": "Not found"})
                return
            export = self.path == "/api/export"
            with closing(sqlite3.connect(database)) as db:
                query = "SELECT record_json FROM inspections ORDER BY created_at DESC"
                rows = db.execute(query if export else query + " LIMIT 50")
                records = [json.loads(row[0]) for row in rows]
            if not export:
                fields = ("inspection_id", "created_at", "source", "classification", "required_action",
                          "llama_status", "screening_decision", "model_score", "probability_defective", "verdict_wall_s")
                records = [{key: record.get(key) for key in fields} for record in records]
            self.reply(200, records, download=export)

        def do_POST(self):
            if self.path != "/api/inspect":
                self.reply(404, {"error": "Not found"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Send JSON inspection input."})
                return
            if storage_failed.is_set():
                self.reply(503, {"error": "Advisory storage unavailable. Restart PillGuard after checking storage."})
                return
            if stopping.is_set() or not inspection_slot.acquire(blocking=False):
                self.reply(503, {"error": "Another inspection is active. Retry shortly."})
                return
            if not advisory_slots.acquire(blocking=False):
                inspection_slot.release()
                self.reply(503, {"error": "Advisory capacity reached. Wait for a completed advisory and retry."})
                return
            queued = False
            try:
                queued = self.inspect_request()
            finally:
                if not queued:
                    advisory_slots.release()
                inspection_slot.release()

        def inspect_request(self):
            start = time.monotonic()
            try:
                self.connection.settimeout(15)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    self.reply(413, {"error": "Image request is too large or empty."})
                    return
                data, source, suffix, shift_note = decode_request(json.loads(self.rfile.read(length)))
            except (ValueError, TimeoutError) as exc:
                self.reply(400, {"error": str(exc)})
                return

            inspection_id = uuid.uuid4().hex
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            try:
                with tempfile.TemporaryDirectory(prefix="pillguard-inspection-") as folder:
                    image = Path(folder) / ("input" + suffix)
                    image.write_bytes(data)
                    result = engine.inspect(image)
                vision_done = time.monotonic()
                record = {
                    "schema_version": "1.1", "inspection_id": inspection_id,
                    "created_at": created_at, "source": source,
                    "shift_note": shift_note,
                    "input_validation": "OPERATOR_CONFIRMED_PILL_PRESENT",
                    "verdict_wall_s": round(vision_done - start, 3),
                    "preprocess_ms": None,
                    "llama_model": engine.llama_runner.name if hasattr(engine, "llama_runner") else None,
                    "llama_status": "PENDING", "llama_explanation": "",
                    "llama_raw_for_review": "", "llama_metrics": {}, "llama_latency_s": None,
                    **result,
                }
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute(
                        "INSERT INTO inspections VALUES (?, ?, ?)",
                        (inspection_id, created_at, json.dumps(record, allow_nan=False)),
                    )
                logging.info("inspection=%s source=%s decision=%s qc=%s llama=%s elapsed=%.3fs",
                             inspection_id, source, result["screening_decision"],
                             result["required_action"], record["llama_status"], record["verdict_wall_s"])
            except Exception:
                logging.exception("Inspection %s failed", inspection_id)
                self.reply(500, {"error": "Inspection failed. See the local PillGuard log."})
                return
            advisory_queue.put_nowait((inspection_id, time.monotonic()))
            try:
                self.reply(200, record)
            except OSError:
                logging.info("Client disconnected after inspection %s was saved", inspection_id)
            return True

        def log_message(self, fmt, *args):
            if self.path != "/api/history":
                logging.info(fmt, *args)

    def start_worker():
        nonlocal recovery_complete
        if not recovery_complete:
            recover_pending()
            thread.start()
            recovery_complete = True

    def stop_worker():
        stopping.set()
        if recovery_complete:
            advisory_queue.put(None)
            thread.join()
        recover_pending()

    if start:
        start_worker()
    Handler.start_worker = staticmethod(start_worker)
    Handler.stop_worker = staticmethod(stop_worker)
    return Handler


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    request_queue_size = 8

    def __init__(self, *args, **kwargs):
        self.connections = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(15)
        try:
            super().process_request(request, address)
        except BaseException:
            self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.connections.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vision-dir", required=True, type=Path)
    parser.add_argument("--llama-runner", required=True, type=Path)
    parser.add_argument("--tokenizer", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address. Default is loopback only; use 0.0.0.0 only on a trusted offline LAN.")
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    database = args.data_dir / "history.sqlite3"
    with (args.data_dir / "service.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another PillGuard process owns this data directory.")
        serve(args, database)


def serve(args, database):
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record_json TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS inspections_created_at ON inspections(created_at)")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.data_dir / "pillguard.log"), logging.StreamHandler()],
    )
    engine = Pipeline(args.vision_dir, args.llama_runner, args.tokenizer)
    handler = make_handler(engine, database, start=False)

    def request_shutdown(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, request_shutdown)
    server = BoundedHTTPServer((args.host, args.port), handler)
    try:
        handler.start_worker()
        logging.info("PillGuard ready at http://%s:%d", args.host, args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
    finally:
        server.server_close()
        handler.stop_worker()


if __name__ == "__main__":
    main()
