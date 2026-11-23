# Actual execution flow

```text
Browser on localhost (or loopback through an SSH tunnel)
  └─ JPEG/PNG data URL + operator confirms tablet + POST /api/inspect
       └─ Python HTTP service validates request and image
            └─ temporary JPEG/PNG -> run_pillguard.py
                 ├─ Pillow/NumPy preprocessing -> little-endian float32 tensor
                 └─ Pi ARM64 C++ ExecuTorch Module, XNNPACK, Experiment 2 forward
                      └─ softmax probabilities, threshold 0.30, binary result
                           └─ Python verifies output and derives deterministic QC
                                ├─ PASS -> STANDARD_QC_REVIEW
                                └─ FAIL -> QUARANTINE
            └─ separate CPU llama_main -> ExecuTorch, Llama 3.2 1B Q4
                 └─ classification-specific constrained advisory -> exact-match gate
            └─ SQLite record -> response, history, and JSON export
```

The binary classification comes from the C++ executable comparing a full-precision score. Python checks the printed class and scores, with a tolerance for threshold rounding. Vision and advisory execute sequentially. Llama receives text derived from the deterministic result, with no tablet pixels or arbitrary user text. A displayed advisory must match the allowed sentence for the classification. Both QC outcomes keep dispensing authorization false. Severity stays unassessed.

- **Baseline, 8765.** The binary uses its first forward result and runs ten further timed forwards. The app returns after advisory and persists the combined record. Historical reference documented in the prior audit.
- **Optimized deployment, 8766.** A rebuilt vision wrapper uses the same first forward and omits the ten timed passes. The Llama prompt is shorter by six tokens per tested case, with the same decisions and approved sentences. The branch uses separate storage. See `app/` and `vision/`.
- **Asynchronous prototype.** Uses the optimized vision executable, prompt and unchanged models. After vision, it commits a pending row and returns HTTP 202 with the decision. The browser shows QC and polls `/api/inspection/<id>`. The background worker writes advisory fields and completion timing only. A single slot covers both heavy subprocesses. Competing requests receive HTTP 409. No model stays resident between inspections. On startup, the prototype marks persisted pending advisory records as interrupted. It was tested in separate directories and ports, and remains outside the two working deployments.

SQLite stores the inspection ID, timestamp, and complete JSON record. The APIs expose a recent history projection and a downloadable JSON export. The offline acceptance evidence tests normal and defective uploaded files, exact deployed hashes, and export equality following restart. Live camera input remains untested because physical hardware was unavailable.
