# PillGuard

Offline tablet defect screening and quality-control support for the Bharat AI-SoC Challenge PS5.

Indian regulators flag tablets as “not of standard quality” for visible problems such as spots and broken tablets, while small manufacturers often inspect samples by hand. PillGuard screens uploaded tablet images for visible defects and records a deterministic quality-control result. It runs offline on a Raspberry Pi 4 Model B with 2 GB RAM, using Arm CPU inference and local storage. A FAIL routes an image to quarantine and a PASS to standard QC review; neither result authorizes dispensing.

## How it works

1. Browser uploads an image to the Python service and confirms a tablet is visible.
2. ExecuTorch runs EfficientNetV2-S with XNNPACK on the Arm Cortex-A72 CPU.
3. A deterministic QC rule compares the defective probability with the configured threshold and returns PASS or FAIL plus the corresponding review action.
4. The inspection is stored in SQLite and is available in history and JSON export.
5. A background ExecuTorch Llama 3.2 1B Q4 worker produces a non-authoritative advisory after the verdict.

## Archived Raspberry Pi 4 measurements

| Measurement | Result | Evidence |
|---|---:|---|
| Vision forward, FP32 XNNPACK | 315 ms mean | [Dataset metrics](evidence/dataset/metrics.json) |
| Test set at threshold 0.30 | 200 images; 83.0% accuracy; 82.0% defect recall; 83.7% precision | [Dataset metrics](evidence/dataset/metrics.json) |
| Llama Q4 prefill / decode | 11.28 / 1.74 tokens/s | [Pi runner log](evidence/pi-q4-16-tokens.log) |
| Llama peak child RSS / model load | about 800 MiB (818,188 KiB) / 17 s | [Pi runner log](evidence/pi-q4-16-tokens.log) |
| Legacy sequential inspection | optimized: 22.1–22.9 s; baseline: 28.3–31.1 s | [Pi offline uploads](evidence/pi-offline-uploads.log) |
| Idle temperature / throttling | 43.8 °C / none observed | [Pi verification](evidence/pi/pi_verification_2026-11-23.txt) |
| Offline acceptance | PASS and FAIL uploads, persistence and export with networking removed | [Offline acceptance](evidence/pi-offline-uploads.log) |

The test split has a flagged possible same-source photograph overlap; see [dataset notes](docs/DATASET.md). Treat its score as provisional.

## Release candidate

The service saves the deterministic vision and QC verdict and returns it without waiting for its advisory. An answer-prefix prompt requests one approved check. The parser separates the exact prompt echo, generated answer and observer metrics. FAIL permits checks 2–5 and always routes the tablet to quarantine. The dashboard labels local Llama and rule fallback separately and retains raw generation in technical details. A single native execution lock protects the 2 GB Pi. A new inspection can wait for an active advisory.

See the [release handoff](docs/PHASE1-RELEASE.md), [advisory experiments](docs/EXPERIMENTS.md), and [Pi and automated evidence](evidence/phase1-rc/).

## Quick start

See [setup and reproducibility](docs/SETUP.md). Real ARM inference needs the matching model, tokenizer, ExecuTorch runtime and Pi deployment artifacts listed in the evidence manifests.

## Repository map

- `app/`: Python HTTP service, QC rules and browser UI
- `vision/`: image preprocessing and ExecuTorch vision runner source
- `models/`: model export and cross-build recipes
- `docs/`: system design, setup, results and validation notes
- `evidence/`: Pi logs, dataset predictions, metrics and acceptance records

## Team roles

| Role | Focus |
|---|---|
| Member 1 | AI/ML, vision model and evaluation |
| Member 2 | Embedded systems, Arm SoC and ExecuTorch deployment |
| Member 3 | Browser interface and integration |

## Limitations

PillGuard is a binary image classifier for visible defects; it does not identify defect subtype. The public dataset may contain source overlap between splits. A fixed camera rig, validated severity estimation and an INT8/thread sweep remain future work. The displayed probability is uncalibrated, and the system is a screening aid rather than pharmaceutical release authority.

## Phase 2 plan

Move to Raspberry Pi 5; build a fixed camera jig with locked exposure; collect an in-house dataset split by physical tablet; measure defect area and severity in mm; compare INT8 with FP32 and XNNPACK with KleidiAI; and score Llama reasoning over shift notes blind against a rule baseline.

See [technical report](docs/TECHNICAL-REPORT.md), [PS5 mapping](docs/PS5-STATUS.md), and [evidence index](evidence/README.md).
