#!/usr/bin/env python3
"""Serve the offline PillGuard UI and its local SQLite inspection history."""
import argparse
import base64
import binascii
import json
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

from PIL import Image, UnidentifiedImageError

from pipeline import Pipeline

HTML = Path(__file__).with_name("index.html").read_bytes()
MAX_BODY = 18 * 1024 * 1024
MAX_IMAGE = 12 * 1024 * 1024
MAX_PIXELS = 16_000_000


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


def make_handler(engine, database):
    advisory_queue = queue.Queue()

    def update_advisory(inspection_id):
        try:
            with closing(sqlite3.connect(database)) as db:
                row = db.execute("SELECT created_at, record_json FROM inspections WHERE id = ?", (inspection_id,)).fetchone()
            if not row:
                return
            current_created_at, raw_record = row
            record = json.loads(raw_record)
            with closing(sqlite3.connect(database)) as db:
                history = db.execute(
                    "SELECT record_json FROM inspections WHERE created_at < ? ORDER BY created_at DESC LIMIT 10",
                    (current_created_at,),
                ).fetchall()
            decisions = [json.loads(item[0]).get("screening_decision") for item in history]
            last10 = sum(value == "FAIL" for value in decisions)
            last3 = sum(value == "FAIL" for value in decisions[:3])
            try:
                fields = engine.advisory(
                    record["screening_decision"], record["probability_defective"], last10, last3,
                    record.get("shift_note", ""),
                )
            except TypeError:
                # Compatibility for lightweight pipeline stand-ins in integrations.
                fields = engine.advisory(record["classification"])
            fields["recent_last10_fails"] = last10
            fields["recent_last3_fails"] = last3
            record.update(fields)
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("UPDATE inspections SET record_json = ? WHERE id = ?",
                           (json.dumps(record, allow_nan=False), inspection_id))
        except Exception:
            logging.exception("Advisory update failed for %s", inspection_id)

    def worker():
        while True:
            inspection_id = advisory_queue.get()
            try:
                update_advisory(inspection_id)
            finally:
                advisory_queue.task_done()

    threading.Thread(target=worker, name="pillguard-llama-worker", daemon=True).start()

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
            if self.path.startswith("/api/inspection/"):
                inspection_id = self.path.rsplit("/", 1)[-1]
                with closing(sqlite3.connect(database)) as db:
                    row = db.execute("SELECT record_json FROM inspections WHERE id = ?", (inspection_id,)).fetchone()
                if row:
                    self.reply(200, json.loads(row[0]))
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
                          "llama_status", "screening_decision", "model_score", "probability_defective", "inspection_wall_s")
                records = [{key: record.get(key) for key in fields} for record in records]
            self.reply(200, records, download=export)

        def do_POST(self):
            if self.path != "/api/inspect":
                self.reply(404, {"error": "Not found"})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Send JSON inspection input."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    self.reply(413, {"error": "Image request is too large or empty."})
                    return
                data, source, suffix, shift_note = decode_request(json.loads(self.rfile.read(length)))
            except ValueError as exc:
                self.reply(400, {"error": str(exc)})
                return

            inspection_id = uuid.uuid4().hex
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            start = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix="pillguard-inspection-") as folder:
                    image = Path(folder) / ("input" + suffix)
                    image.write_bytes(data)
                    result = engine.inspect(image)
                vision_done = time.monotonic()
                record = {
                    "schema_version": "1.0", "inspection_id": inspection_id,
                    "created_at": created_at, "source": source,
                    "shift_note": shift_note,
                    "input_validation": "OPERATOR_CONFIRMED_PILL_PRESENT",
                    "inspection_wall_s": round(vision_done - start, 3),
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
                             result["required_action"], record["llama_status"], record["inspection_wall_s"])
            except Exception:
                logging.exception("Inspection %s failed", inspection_id)
                self.reply(500, {"error": "Inspection failed. See the local PillGuard log."})
                return
            advisory_queue.put(inspection_id)
            self.reply(200, record)

        def log_message(self, fmt, *args):
            if self.path != "/api/history":
                logging.info(fmt, *args)

    return Handler


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
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, record_json TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS inspections_created_at ON inspections(created_at)")
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.data_dir / "pillguard.log"), logging.StreamHandler()],
    )
    engine = Pipeline(args.vision_dir, args.llama_runner, args.tokenizer)
    with ThreadingHTTPServer((args.host, args.port), make_handler(engine, database)) as server:
        logging.info("PillGuard ready at http://%s:%d", args.host, args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
