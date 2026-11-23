# System architecture

```text
Browser (on the Pi, or on a laptop through an SSH tunnel to localhost)
  └─ image upload + operator confirmation + optional shift note → POST /api/inspect
       └─ Python HTTP service validates image and operator confirmation
            └─ Pillow + NumPy preprocessing → float32 1 × 3 × 224 × 224 tensor
                 └─ C++ ExecuTorch EfficientNetV2-S + XNNPACK on Cortex-A72
                      └─ defective probability → fixed threshold 0.30 → PASS or FAIL
                           └─ deterministic QC action
                                ├─ PASS → STANDARD_QC_REVIEW
                                └─ FAIL → QUARANTINE
       ├─ SQLite record → response returned (verdict first); history and JSON export
       └─ background worker: ExecuTorch Llama 3.2 1B Q4
            └─ result + FAIL count in the 10 earlier inspections + shift note
                 → approved-check number 1–5 (invalid reply → rule baseline) → record update
```

The vision result and QC rule determine the verdict and required action. The C++ executable compares a full-precision score with the threshold; Python checks the printed class and scores, with a tolerance for threshold rounding.

The service admits one inspection request and reserves one of two advisory slots before reading the image. A FIFO worker generates advisories after the corresponding verdict is stored. Vision and Llama share one inference lock. A request can therefore wait behind active Llama execution. Further inspections receive HTTP 503 while admission or advisory capacity is occupied. The service also bounds active HTTP connections and applies read and native-process deadlines.

The prompt receives the verdict, preceding FAIL counts and a length-limited, normalized operator observation. On success the parser isolates the generation following the exact echo and separates the observer report. The response grammar accepts one verdict-compatible option with an optional approved label. FAIL excludes option 1 in both the prompt and validator. Unsupported output, execution failure, timeout or interruption uses an approved rule fallback. The worker can write only advisory fields. The approved text asks for a human check, while the raw model text and diagnostics stay in technical details and export. Dispensing authorization remains false and severity stays `NOT_ASSESSED`.

SQLite uses WAL and a per-data-directory process lock. Startup recovers interrupted pending jobs to terminal fallback. Graceful shutdown drains admitted requests and joins the worker. Timed-out native process groups are killed and reaped. The browser polls the selected inspection ID, discards stale responses and requests day totals using the browser’s local calendar boundaries. History shows 50 recent rows and export includes all rows.

See [UI behavior](UI-CHANGES.md), [technical report](TECHNICAL-REPORT.md), and [release handoff](PHASE1-RELEASE.md).
