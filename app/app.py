#!/usr/bin/env python3
"""Serve the offline PillGuard UI and its local SQLite inspection history."""
import argparse
import base64
import binascii
import json
import logging
import sqlite3
import tempfile
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
    return data, source, suffix


def make_handler(engine, database):
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
            if self.path not in ("/api/history", "/api/export"):
                self.reply(404, {"error": "Not found"})
                return
            export = self.path == "/api/export"
            with closing(sqlite3.connect(database)) as db:
                query = "SELECT record_json FROM inspections ORDER BY created_at DESC"
                rows = db.execute(query if export else query + " LIMIT 50")
                records = [json.loads(row[0]) for row in rows]
            if not export:
                fields = ("created_at", "source", "classification", "required_action",
                          "llama_status", "screening_decision", "model_score")
                records = [{key: record[key] for key in fields} for record in records]
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
                data, source, suffix = decode_request(json.loads(self.rfile.read(length)))
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
                record = {
                    "schema_version": "1.0", "inspection_id": inspection_id,
                    "created_at": created_at, "source": source,
                    "input_validation": "OPERATOR_CONFIRMED_PILL_PRESENT",
                    "inspection_wall_s": round(time.monotonic() - start, 3),
                    **result,
                }
                with closing(sqlite3.connect(database)) as db, db:
                    db.execute(
                        "INSERT INTO inspections VALUES (?, ?, ?)",
                        (inspection_id, created_at, json.dumps(record, allow_nan=False)),
                    )
                logging.info("inspection=%s source=%s decision=%s qc=%s llama=%s elapsed=%.3fs",
                             inspection_id, source, result["screening_decision"],
                             result["required_action"], result["llama_status"], record["inspection_wall_s"])
            except Exception:
                logging.exception("Inspection %s failed", inspection_id)
                self.reply(500, {"error": "Inspection failed. See the local PillGuard log."})
                return
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
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(engine, database)) as server:
        logging.info("PillGuard ready at http://localhost:%d", args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
