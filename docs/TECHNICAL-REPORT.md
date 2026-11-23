# PillGuard technical report · Phase 1, PS5

## Problem

Visible tablet defects such as spots and breakage can lead regulators to classify products as not of standard quality. Small manufacturers may inspect samples manually. PillGuard is an offline screening prototype that classifies an uploaded tablet image as normal or defective and records the resulting QC route on a Raspberry Pi 4 Model B with 2 GB RAM.

## System design

The browser sends an image to a Python HTTP service. Pillow and NumPy decode RGB, resize to 224 × 224, normalize with ImageNet mean and standard deviation, and produce a contiguous float32 CHW tensor. A C++ ExecuTorch Module runs EfficientNetV2-S through XNNPACK on the Cortex-A72. Python validates the output and applies the configured 0.30 defective-probability threshold. PASS maps to standard QC review; FAIL maps to quarantine. Neither permits dispensing.

The inspection record is stored in SQLite and exposed through history and JSON export. The verdict-first path returns after vision and deterministic QC; an independent background worker generates and stores the Llama advisory. The current archived Pi measurements also include the earlier sequential path, where advisory generation completes before the request returns.

## Arm and ExecuTorch deployment

The vision model is exported as a float32 forward graph and deployed in the AArch64 ExecuTorch 1.6.0 runtime with XNNPACK. The Pi verification log records 315 ms mean vision forward latency over the 200-image test set. A wrapper parity log records identical printed probabilities and decisions between the tested wrappers.

Llama 3.2 1B Instruct is exported for ExecuTorch with 8da4w weight quantization, group size 128, 4-bit embedding quantization with groups of 32, float32 override, KV cache, and XNNPACK lowering. The runtime uses four CPU threads. One logged generation measured 11.28 tokens/s prefill and 1.74 tokens/s decode; model loading took about 17 seconds and peak child RSS was about 800 MiB (818,188 KiB). These are process-level measurements on the 2 GB Pi, not a total application memory guarantee.

The standalone runner was cross-compiled for AArch64 Cortex-A72 using Arm GNU `aarch64-none-linux-gnu` compilers and the toolchain-provided Linux sysroot. `ldd` on the Pi confirms runtime shared-library resolution against the deployed ExecuTorch environment and Pi system libraries; the tested system reports glibc 2.41 ([Pi dependency inventory](../evidence/rollback/pi-checkpoint.log)). The Llama runner uses four CPU threads, and export used `OMP_NUM_THREADS=2`. Build configuration and artifact hashes are recorded in [the runner configuration log](../evidence/pillguard-release-runner-config.log), [cross-build recipe](../models/llama-build/README.md), and [Pi manifest](../evidence/pi-sha256.txt). The exported model and runner use the original tokenizer. The Pi idle check recorded 43.8 °C and no throttling.

## Results

| Measurement | Result | Evidence |
|---|---:|---|
| Vision forward, FP32 XNNPACK | 315 ms mean | [Dataset metrics](../evidence/dataset/metrics.json) |
| Test set at threshold 0.30 | 200 images; 83.0% accuracy; 82.0% defect recall; 83.7% precision | [Dataset metrics](../evidence/dataset/metrics.json) |
| Confusion matrix at threshold 0.30 | TP 82, FN 18, FP 16, TN 84 | [Dataset metrics](../evidence/dataset/metrics.json) |
| Llama Q4 prefill / decode | 11.28 / 1.74 tokens/s | [Pi runner log](../evidence/pi-q4-16-tokens.log) |
| Llama peak child RSS / model load | about 800 MiB (818,188 KiB) / 17 s | [Pi runner log](../evidence/pi-q4-16-tokens.log) |
| Legacy sequential inspection | optimized: 22.1–22.9 s; baseline: 28.3–31.1 s | [Pi offline uploads](../evidence/pi-offline-uploads.log) |
| Idle temperature / throttling | 43.8 °C / none observed | [Pi verification](../evidence/pi/pi_verification_2026-11-23.txt) |
| Offline acceptance | PASS and FAIL uploads, persistence and export with networking removed | [Offline acceptance](../evidence/pi-offline-uploads.log) |

The test confusion matrix is TP=82, FN=18, FP=16, TN=84. Dataset audit notes identify a possible same-source image crossing train/test; the reported test metrics are therefore provisional. Offline acceptance removed networking and verified uploads, stored records and export behavior. The old sequential app path takes 22.1–22.9 seconds in the optimized run and 28.3–31.1 seconds in the baseline run because each request waits for Llama startup and generation.

## Current release candidate on the Pi

Three consecutive inspections completed on ARM64 with only loopback in the process namespace. First-service and warm idle HTTP verdicts were 1.227 s and 1.187 s. The next request waited 19.999 s while the prior Llama process used the sole native execution slot. Vision forward stayed within 324.311–327.111 ms. Llama runner wall time ranged from 18.966 to 19.367 s. Two advisories were accepted and one used safe fallback. Sampled available memory stayed above 896 MiB. No swap use increase or OOM event was observed. This small run does not establish sustained throughput. [Pi trace and manual checklist](PHASE1-RELEASE.md)

## Llama role and evaluation method

The Llama model never sets the screening verdict or required action. The thresholded vision result and deterministic rule select PASS/standard QC review or FAIL/quarantine. Llama receives text context and returns a constrained, non-authoritative advisory that is stored separately from the decision.

The RC evaluates the answer-prefix prompt against 12 development and four additional held-out scenarios using the same grammar in production and evaluation. Its data and limitations are reported in [experiments](EXPERIMENTS.md). The controlled Pi end-to-end run and serialized-inference trade-off are in the [release handoff](PHASE1-RELEASE.md).

## Limitations

The classifier distinguishes only normal from defective and does not label defect subtype. The public dataset may contain source overlap, so independent performance remains to be measured. Acceptance used uploads, not a fixed camera jig with controlled exposure. Severity and area measurement are not yet validated. Probabilities are uncalibrated. PASS is a screening result and never authorizes dispensing. The legacy sequential timing reflects the earlier synchronous path; the RC separately measures idle and contended verdict latency. INT8, thread sweeps and severity measurement remain future work.

## Phase 2 plan

Target Raspberry Pi 5 and a fixed camera jig with locked exposure. Collect an in-house dataset and split by physical tablet to prevent image-level leakage. Measure defect area and severity in mm. Compare INT8 with FP32 and XNNPACK with KleidiAI, including a 1→4 thread sweep. Evaluate Llama reasoning over shift notes blind against the rule baseline and report scenario-level results.
