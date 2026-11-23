# System architecture

```text
Browser
  └─ image upload /api/inspect
       └─ Python HTTP service validates image and operator confirmation
            └─ Pillow + NumPy preprocessing → float32 1 × 3 × 224 × 224 tensor
                 └─ C++ ExecuTorch EfficientNetV2-S + XNNPACK on Cortex-A72
                      └─ defective probability → fixed threshold → PASS or FAIL
                           └─ deterministic QC action
                                ├─ PASS → STANDARD_QC_REVIEW
                                └─ FAIL → QUARANTINE
       ├─ SQLite record; history and JSON export
       └─ background ExecuTorch Llama 3.2 1B Q4 advisory → record update
```

The vision result and QC rule determine the verdict and required action. Llama receives text derived from the result; it does not inspect image pixels, set PASS/FAIL, or change the action. Its output is an advisory. In the current implementation, an exact-match gate limits displayed output to the approved sentence for that class. Parallel `llama-check` work explores selecting one of five approved QC checks from the recent FAIL trend and an operator shift note, with a rule-based fallback.

The HTTP response returns after vision and QC. The Llama worker updates advisory fields asynchronously, and the browser polls `/api/inspection/<id>`. SQLite persists inspections, including the independent status of the advisory. A failed or pending advisory does not change the recorded QC result. Dispensing authorization remains false for both outcomes.

The browser supports image uploads, camera capture and video-frame capture. Recorded Pi acceptance and performance evidence used image uploads. See [UI changes](UI-CHANGES.md), [measured results](TECHNICAL-REPORT.md), and [offline evidence](../evidence/README.md).
