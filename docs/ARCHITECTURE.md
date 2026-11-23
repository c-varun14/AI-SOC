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

The HTTP response returns after vision and QC. One background worker runs Llama, so only one Llama process is ever in memory, and the browser polls `/api/inspection/<id>` until the advisory arrives. Llama receives text derived from the result; it does not see image pixels, set PASS/FAIL, or change the action. It receives the deterministic result, FAIL counts from up to ten earlier inspections, and a shift note capped at 160 characters with chat-template tokens removed. The first digit of its reply selects one of five approved checks; any other reply, a timeout or an error falls back to the Python rule baseline, and the UI shows which one chose. A failed or pending advisory never changes the recorded QC result. Dispensing authorization remains false for both outcomes, and severity is not yet assessed.

SQLite stores the inspection ID, timestamp and complete JSON record, including the advisory status. The APIs expose a recent-history projection and a downloadable JSON export. The browser supports image uploads, camera capture and video-frame capture; recorded Pi acceptance and performance evidence used image uploads. Llama accuracy on the 12 seeded scenarios in `eval/` has not yet been measured on the Pi.

See [UI changes](UI-CHANGES.md), [measured results](TECHNICAL-REPORT.md), and [offline evidence](../evidence/README.md).
