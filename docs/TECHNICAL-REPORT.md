# PillGuard technical report · Phase 1, PS5

PillGuard is an offline binary tablet-screening prototype. It runs on Raspberry Pi 4 Model B with 2 GB RAM. The submission reference is the optimized upload deployment whose prior Pi service used loopback port 8766. The matching application, single-pass vision wrapper and advisory filter are in this repository.

A browser upload passes to the Python service. Pillow and NumPy resize and normalize RGB to a float32 tensor. An ARM64 ExecuTorch 1.6.0 XNNPACK runner executes EfficientNetV2-S Experiment 2. The 0.30 defective probability cutoff produces a binary classification. Python maps it deterministically to standard QC review or quarantine. A separate Llama 3.2 1B Instruct Q4 ExecuTorch process generates the advisory with a classification-specific prompt. The app displays only an approved sentence and records the result, timing and advisory status in SQLite. Dispensing authorization always remains false. [Architecture](ARCHITECTURE.md) · [Model metadata and hashes](MODELS.md)

## Measured results from the prior Pi deployment

| Evidence | Result |
|---|---|
| Candidate upload in a loopback-only network namespace | Normal PASS, standard QC review, 22.11 s. Defective FAIL, quarantine, 22.86 s. Accepted advisory in both cases. |
| Persistent history | SQLite integrity and record-for-record JSON export equality passed after restart. |
| Vision dataset evaluation, threshold 0.30 | Test TP 82, FN 18, FP 16, TN 84. Accuracy 83.0%, defect recall 82.0%. Probable source overlap limits this result. |
| Optimized vision parity | All 260 stored validation and test probabilities and decisions reproduced at printed precision. |
| Isolated early-QC prototype | 1.21–1.27 s for local HTTP QC response, about 22–23 s to observed advisory completion. Separate prototype evidence. |

An earlier standalone Q4 run proved real generation on ARM64. The official PS5 technical requirement for on-device Llama via ExecuTorch is evidenced by the Q4 run and offline records. Defect subtype and severity remain unassessed. Sustained real-time throughput and independent accuracy remain unverified. Live physical-camera capture remains untested because hardware was unavailable. Uploads are the verified demonstration workflow. [Offline acceptance](../evidence/pi-offline-uploads.log) · [Standalone Q4](../evidence/pi-q4-16-tokens.log) · [Dataset audit](DATASET.md) · [PS5 coverage](PS5-STATUS.md)

The later development-only safety fixes and structured advisory experiment are outside the release. [Experiment record](EXPERIMENTS.md)
