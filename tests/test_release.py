"""Exercise the shipped HTTP and QC path using synthetic native-runner stand-ins."""
import base64
from contextlib import closing
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from app import make_handler
from pipeline import Pipeline, THRESHOLD


class ReleaseSmoke(unittest.TestCase):
    def test_upload_store_export(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            shutil.copy(ROOT / "vision/run_pillguard.py", tmp)
            shutil.copy(ROOT / "vision/preprocess_pill_deployment.py", tmp)
            (tmp / "build").mkdir()
            vision = tmp / "build/pillguard_deployment_inference"
            vision.write_text(f"""#!{sys.executable}
import pathlib, sys
data = pathlib.Path(sys.argv[1]).read_bytes()
assert len(data) == 1 * 3 * 224 * 224 * 4
import struct
defective = struct.unpack_from("<f", data)[0] > 0
print("Forward latency: 1 ms")
print("Threshold: 0.3")
print("Defective probability:", 0.8 if defective else 0.1)
print("Normal probability:", 0.2 if defective else 0.9)
print("Prediction:", "DEFECTIVE" if defective else "NORMAL")
""")
            vision.chmod(0o700)
            llama = tmp / "llama_main"
            llama.write_text(f"""#!{sys.executable}
import sys
import time
time.sleep(.25)
prompt = sys.argv[sys.argv.index("--prompt") + 1]
assert "Copy exactly:" in prompt
advice = "The tablet was classified as normal and should continue to standard quality review."
if "flagged as defective" in prompt:
    advice = "Unsupported advisory must be rejected."
print(prompt + advice)
print("PyTorchObserver {{}}")
""")
            llama.chmod(0o700)
            database = tmp / "history.sqlite3"
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("CREATE TABLE inspections (id TEXT PRIMARY KEY, created_at TEXT, record_json TEXT)")
            pipeline = Pipeline(tmp, llama, tmp / "tokenizer.model")
            with ThreadingHTTPServer(("127.0.0.1", 0), make_handler(pipeline, database)) as server:
                worker = threading.Thread(target=server.serve_forever)
                worker.start()
                try:
                    url = f"http://127.0.0.1:{server.server_port}"
                    responses = []
                    for color, decision, action, advisory in (
                        ("black", "PASS", "STANDARD_QC_REVIEW", "COMPLETED_DISPLAYED"),
                        ("white", "FAIL", "QUARANTINE", "COMPLETED_NOT_APPROVED"),
                    ):
                        buffer = BytesIO()
                        Image.new("RGB", (4, 4), color).save(buffer, "PNG")
                        encoded = base64.b64encode(buffer.getvalue()).decode()
                        payload = {"source": "upload", "pill_present_confirmed": True,
                                   "image": "data:image/png;base64," + encoded}
                        request = Request(url + "/api/inspect", json.dumps(payload).encode(),
                                          {"Content-Type": "application/json"})
                        with urlopen(request, timeout=20) as response:
                            record = json.load(response)
                        self.assertEqual(record["screening_decision"], decision)
                        self.assertEqual(record["required_action"], action)
                        self.assertEqual(record["threshold"], THRESHOLD)
                        self.assertIs(record["dispensing_authorized"], False)
                        self.assertEqual(record["llama_status"], "PENDING")
                        self.assertIn("vision_forward_ms", record)
                        self.assertIn("verdict_wall_s", record)
                        status_url = url + "/api/inspection/" + record["inspection_id"]
                        for _ in range(100):
                            with urlopen(status_url, timeout=5) as response:
                                final = json.load(response)
                            if final["llama_status"] != "PENDING":
                                break
                            time.sleep(.03)
                        self.assertEqual(final["llama_status"], advisory)
                        self.assertEqual(bool(final["llama_explanation"]), decision == "PASS")
                        responses.append(final)
                    with urlopen(url + "/api/system", timeout=5) as response:
                        system = json.load(response)
                    self.assertIsInstance(system, dict)
                    self.assertIn("cpu_architecture", system)
                    with urlopen(url + "/api/export", timeout=5) as response:
                        self.assertEqual(json.load(response), responses[::-1])
                finally:
                    server.shutdown()
                    worker.join()

    def test_advisory_failures_do_not_touch_verdict_fields(self):
        engine = Pipeline("/tmp", "/tmp/llama", "/tmp/tokenizer")
        verdict = {"screening_decision": "FAIL", "required_action": "QUARANTINE",
                   "dispensing_authorized": False}
        with patch("pipeline.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("llama", 90)):
            advisory = engine.advisory("defective")
        self.assertEqual(advisory["llama_status"], "TIMEOUT")
        self.assertEqual(verdict, {"screening_decision": "FAIL", "required_action": "QUARANTINE",
                                   "dispensing_authorized": False})
        class Completed:
            returncode = 0
            stdout = "garbage"
            stderr = ""
        with patch("pipeline.subprocess.run", return_value=Completed()):
            advisory = engine.advisory("defective")
        self.assertEqual(advisory["llama_status"], "ERROR")
        self.assertEqual(verdict["screening_decision"], "FAIL")
        self.assertEqual(verdict["required_action"], "QUARANTINE")
        self.assertIs(verdict["dispensing_authorized"], False)


if __name__ == "__main__":
    unittest.main()
