# PillGuard · Bharat AI-SoC Challenge PS5

PillGuard screens uploaded tablet images on a Raspberry Pi 4 Model B with 2 GB RAM. EfficientNetV2-S Experiment 2 and Llama 3.2 1B Instruct Q4 run offline through separate ExecuTorch processes. The vision threshold determines the binary screening result. Deterministic logic selects standard QC review or quarantine. The model score and advisory are stored with each inspection and can be exported from the browser.

This source tree stages the previously verified optimized deployment for **Phase 1 Open Qualifying**. Its compact Llama prompt and exact-match advisory filter are preserved. The subsequent experimental advisory and development-only safety changes are outside this revision.

PS5 addresses industrial defect detection and quality control. PillGuard applies it to visible tablet defects. The binary screening output directs a tablet to standard quality review or quarantine. Dispensing authorization stays false for both results.

| Team role | Responsibility |
|---|---|
| Member 1 | AI/ML, vision model and evaluation |
| Member 2 | Embedded systems, Arm SoC and ExecuTorch deployment |
| Member 3 | Browser interface and integration |

| Start here | What it covers |
|---|---|
| [Setup and tests](docs/SETUP.md) | WSL review, hardware-dependent setup, and the locked release files. See [WSL verification](docs/WSL-VERIFICATION.md). |
| [Architecture](docs/ARCHITECTURE.md) | Browser, vision, deterministic QC, Llama, SQLite |
| [Technical report](docs/TECHNICAL-REPORT.md) | Measured Pi performance and limitations |
| [Demo and evidence](evidence/README.md) | Upload walkthrough video, PDF addendum, offline logs, hashes |
| [Models and exports](docs/MODELS.md) | Artifact identification and export recipes |
| [Rights and attribution](notices/RIGHTS.md) | Source, data, pretrained weights and demo image provenance |
| [Submission checklist](docs/SUBMISSION.md) | Official requirements, evidence status and approvals |

The repository contains source, recorded evidence and manifests. Model artifacts, runtime binaries, the dataset archive and private inspection databases are kept with their authorized owners. A local or hosted checkout can run tests with synthetic runner stand-ins. ARM64 application inference requires the identified models, tokenizer and runtime artifacts.
