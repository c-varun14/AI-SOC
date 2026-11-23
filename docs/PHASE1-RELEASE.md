# PillGuard Phase 1 release candidate

**Status:** Prepared for final joint Raspberry Pi and phone acceptance. The submission deadline is **25 November 2026, 11:59 p.m. IST**. The official demo still needs to be recorded. The organizer evaluates the first submission.

## Candidate and evidence

- Base revision `6275b2ea62f7c5aef7146b295b7fa5d0216fe8c1` on `phase1-upgrade`.
- Tested application, evaluation, and test code revision `0b052190211f7857caf92c2a8d61d1d60f231a5a` on local `phase1-release-candidate`.
- Vision preprocessing, class mapping, threshold 0.30, models and native runtime reused. FAIL remains quarantine, PASS remains standard QC review, dispensing stays false, and severity remains `NOT_ASSESSED`.
- [Experiment results](EXPERIMENTS.md), [PS5 checklist](PS5-STATUS.md), [WSL tests](../evidence/phase1-rc/wsl-unittest.log), and [mobile-width Chrome test](../evidence/phase1-rc/chrome-mobile.log). The WSL and Chrome suites used stand-ins. The Pi probe uses native inference and separate inspection storage.

## Pi verification

The committed RC ran three native inspections on the ARM64 Pi 4B inside a private network namespace with only loopback. The original Wi-Fi and SSH paths remained available. The earlier review database still contained six records. The Pi LAN proxy smoke test served the RC dashboard and system endpoint through port 18776. It was stopped after verification. [Pi hardware report](../evidence/phase1-rc/hardware.json) · [Service log](../evidence/phase1-rc/service.log) · [LAN smoke log](../evidence/phase1-rc/pi-lan-smoke.log)

| Inspection | HTTP verdict | Vision forward | Llama execution | Outcome |
|---|---:|---:|---:|---|
| First after service start | 1.227 s | 327.111 ms | 19.367 s | PASS, accepted local advisory |
| Warm, submitted while idle | 1.187 s | 324.311 ms | 18.966 s | FAIL, quarantine with approved fallback |
| Submitted while previous Llama was active | 19.999 s | 324.860 ms | 19.292 s | PASS, accepted local advisory |

The server became ready in 0.352 s. The first inspection was service-cold with uncontrolled OS file cache. Native model loading measured 9.654–9.726 s, and observer inference measured 8.925–9.321 s. The advisory queue delay for these cases was 0.003 s each. The contended verdict waited for the prior native process, so that wait is included in server verdict time. Simultaneous native execution was outside this RC measurement.

Available memory was about 1.57 GiB at service readiness and reached a sampled low of 897 MiB. The sampled maximum Llama RSS was 799 MiB, vision RSS was 160 MiB and summed RC process RSS peaked at 828 MiB. Sampled swap use remained zero, Linux swap and OOM counters stayed unchanged, and service exit was zero with no sampled child processes remaining. SoC temperature ranged from 46.3 to 69.1 °C. Firmware reported `0x80000` at both endpoints, a prior soft-temperature-limit event with no active bits in those readings. [Raspberry Pi firmware flags](https://www.raspberrypi.com/documentation/computers/os.html#get_throttled)

This is a three-case controlled run. Real phone capture, repeated mobile workflow and extended thermal stability remain manual acceptance checks.

## Launch for manual acceptance

Run on the team Pi. The staged RC source is in a new directory. It reuses the review workspace’s verified artifact links. The command uses a separate database and port. Stop the foreground service with Ctrl+C and allow active native work to finish.

```sh
cd "$HOME/PillGuard_Phase1_RC.z1lFCv/source-rc"
exec python3 app/app.py \
  --vision-dir "$HOME/PillGuard_Phase1_UI_Review/vision" \
  --llama-runner "$HOME/PillGuard_Llama/et160-a72.aL7oXF/llama_main" \
  --tokenizer "$HOME/PillGuard_Llama/tokenizer.model" \
  --data-dir "$HOME/PillGuard_Phase1_RC.z1lFCv/manual-data" \
  --host 127.0.0.1 --port 18775
```

Run the foreground proxy from another Pi terminal on the trusted demo LAN. Stop it with Ctrl+C after acceptance.

```sh
exec socat TCP-LISTEN:18776,bind=10.188.40.215,reuseaddr,fork TCP:127.0.0.1:18775
```

Phone URL after launch: `http://10.188.40.215:18776`. Camera permission in the browser requires a secure origin. On the HTTP phone URL, use the phone’s camera app and upload its JPEG, or load a local video and capture a frame. If the Pi’s LAN address changes, update the proxy bind address and phone URL.

## Rollback

Stop the two foreground RC commands with Ctrl+C. The original upgraded review is already available at `http://10.188.40.215:18774`. Check from the Pi with `curl -fsS http://127.0.0.1:18773/api/system`. The RC database remains in its separate directory. The protected deployments on ports 8765 and 8766 are outside this procedure.

## Manual acceptance

1. Open the RC on the real phone. Take a JPEG with the phone camera and upload it. Confirm the tablet is visible. Check that the preview and operator confirmation are required.
2. Run the prechecked normal and defective images. Confirm PASS/standard QC review and FAIL/quarantine at the fixed threshold. Verify the QC verdict is locked while each advisory is pending and after it completes or falls back.
3. Load a short local video. Pause, capture a frame, confirm, and inspect. Switch between image and video once. Check two result rows and the downloaded JSON export.
4. Check readable mobile layout, local time and daily counts. Confirm verdict, forward, queue and Llama durations are separate. Verify a network-interface label describes link state.
5. Keep phone and Pi on the same local network and use a local-only access point if an end-to-end phone offline demonstration is needed. Confirm Wi-Fi and SSH remain reachable. Wait for advisories between footage takes; if the demonstration shows a jump cut, label the elapsed time.
6. Review accepted Llama text or the explicit fallback label, required action, and raw response in technical details. Preserve screenshots and the export from the manual data directory.

## Submission checklist

- [x] Prepare the local RC and release evidence. Existing GitHub `main` is public at the archived hardware-evidence revision.
- [ ] Finish manual phone and hardware acceptance and decide which revision the team authorizes for publication.
- [ ] Record the official two-minute demo from the accepted release. Review text, artifacts and measured claims with the team.
- [ ] After approval, publish the authorized source and video links and verify reviewer access.
- [ ] Attach the reviewed Phase 1 report, enter registered team information in the [organizer form](https://forms.gle/3KyscquPFG8rS9ASA), and secure team approval before the first submission.
- [ ] Save the confirmation privately.

## Official demo recording plan

Record in 1080p, 16:9 where practical. Capture fresh footage of the accepted release and retain the complete unedited recordings as evidence.

| Time | Show |
|---|---|
| 0:00–0:13 | Project, Pi 4B and phone on the local LAN. State the binary visual-screening scope. |
| 0:13–0:37 | Use the phone camera to take a tablet photo. Open the dashboard, select the JPEG, confirm and inspect. Show the verdict and timing. |
| 0:37–1:02 | Inspect a prechecked defective sample or captured local video frame. Show FAIL and quarantine before the advisory. |
| 1:02–1:27 | Show the completed approved advisory or explicit fallback, provenance, and the unchanged QC action. Identify the local ExecuTorch model and runner from actual device evidence. |
| 1:27–1:47 | Show history and JSON export. Briefly present measured idle and contended timing. |
| 1:47–2:00 | State binary scope, human confirmation, provisional dataset metrics and attribution for any dataset media shown. |
