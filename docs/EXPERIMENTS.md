# Parallel engineering work

The archived Pi deployment uses a compact prompt and exact-match advisory gate. The sequential Pi measurements remain useful as a baseline.

The verdict-first flow returns PASS/FAIL after vision and deterministic QC, then updates the record when the background Llama advisory completes. An isolated prototype log records roughly 1.2 seconds to QC readiness; timing on the current release path is **[to measure 24 Nov]**. See [UI changes](UI-CHANGES.md) and the [prototype evidence](../evidence/isolated-async-reference.log).

The `llama-check` work selects one of five approved QC checks from recent FAIL trends and an operator shift note. A rule-based fallback is included, and the proposed 12-scenario scoring result is **[to measure 24 Nov]**.

The team is measuring INT8 versus FP32, a 1→4 thread sweep, and severity from measured defect area. These results are **[to measure 24 Nov]**.

A structured advisory experiment in WSL produced no accepted answers on its two prior fixtures. The display gate suppressed both, and deterministic QC remained unchanged. This result is recorded as an experiment, not a deployed capability.
