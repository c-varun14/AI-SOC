# Operator interface and verdict-first flow

The inspection endpoint returns the deterministic vision and QC verdict as soon as those stages finish. Advisory generation runs in one FIFO background worker, and its status and advisory fields are written back to the SQLite record. `GET /api/inspection/<id>` supports polling; `GET /api/system` reports Linux device, CPU, memory, temperature, uptime and non-loopback interface status. Records include vision and verdict timings plus advisory latency and model metrics.

The single-file UI uses offline system fonts and inline SVG. It presents PASS/FAIL before the Llama advisory, device status, pipeline timings, advisory progress, session counts and history. Upload, camera capture, video-frame capture, operator confirmation, history refresh, JSON export and technical details are available.

An isolated prototype log records approximately 1.2 seconds to QC readiness with networking removed. The current release-path measurement is **[to measure 24 Nov]**. The older sequential upload runs took 22.1–22.9 seconds in the optimized run and 28.3–31.1 seconds in the baseline run because the request waited for Llama load and generation. See [prototype evidence](../evidence/isolated-async-reference.log) and [Pi upload evidence](../evidence/pi-offline-uploads.log).
