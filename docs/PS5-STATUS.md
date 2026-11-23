# PS5 requirement mapping

| PS5 requirement or capability | How PillGuard meets it | Evidence |
|---|---|---|
| Edge AI on Arm hardware | EfficientNetV2-S runs through ExecuTorch and XNNPACK on Raspberry Pi 4 Model B, using the Arm Cortex-A72 CPU. | [Pi verification](../evidence/pi/pi_verification_2026-11-23.txt) · [Vision parity](../evidence/pi-vision-parity.log) |
| Llama through ExecuTorch on device | Llama 3.2 1B Instruct Q4 runs locally through an AArch64 ExecuTorch runner. | [Llama inference](../evidence/pi-q4-16-tokens.log) · [Export details](../evidence/llama-export.log) |
| Defect detection | The binary classifier screens visible tablet defects and returns deterministic PASS or FAIL at the configured threshold. | [Dataset metrics](../evidence/dataset/metrics.json) · [Dataset audit](DATASET.md) |
| Quality-control recommendations | PASS routes to standard QC review; FAIL routes to quarantine. Llama supplies a separate advisory and cannot change the verdict or action. | [Offline upload acceptance](../evidence/pi-offline-uploads.log) · [Architecture](ARCHITECTURE.md) |
| Logging and review | SQLite stores inspection records; history and JSON export were checked across restart. | [Offline acceptance](../evidence/offline-acceptance-results.json) |
| Offline edge operation | Upload acceptance ran with networking removed and verified normal and defective cases. | [Pi offline log](../evidence/pi-offline-uploads.log) |
| Real-time edge operation | Vision forward is measured on Pi. Earlier sequential inspections took 22–28 seconds; verdict-first prototype returns QC in about 1.2 seconds, with current release-path timing pending. | [Dataset metrics](../evidence/dataset/metrics.json) · [Sequential uploads](../evidence/pi-offline-uploads.log) · [Verdict-first prototype](../evidence/isolated-async-reference.log) |
| Defect subtype and severity | Phase 1 reports a binary label. Severity measurement is planned and pending. | [Limitations and Phase 2](TECHNICAL-REPORT.md) |
| Physical camera input | Browser camera and video-frame controls exist; recorded Pi acceptance used uploads. A fixed camera setup is planned for Phase 2. | [UI description](UI-CHANGES.md) · [Phase 2 plan](TECHNICAL-REPORT.md) |
| PS5 implementation and results | System design, deployment measurements, limitations and next steps are documented in this repository. | [Technical report](TECHNICAL-REPORT.md) · [Evidence index](../evidence/README.md) |

The model test set has a possible source-overlap finding, so its metrics are provisional. Independent, specimen-level evaluation is described in the [validation plan](INDEPENDENT-VALIDATION.md).
