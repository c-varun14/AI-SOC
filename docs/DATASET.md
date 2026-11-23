# Dataset evidence

Defective is the positive class. These confusion matrices can be recomputed with `python3 evidence/dataset/evaluate.py evidence/dataset/*predictions.csv` from the archive root. This command reads the stored predictions.

| Set | Decision threshold | TP | FN | FP | TN | Accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Validation, 60 images | 0.30 | 26 | 4 | 7 | 23 | 81.67% |
| Test, 200 images | 0.30 | 82 | 18 | 16 | 84 | 83.00% |
| Validation, 60 images | 0.35 | 25 | 5 | 4 | 26 | 85.00% |
| Test, 200 images | 0.35 | 81 | 19 | 13 | 87 | 84.00% |

The original audit flags a probable same-source train/test photograph. The matching test tensor is `normal_023.bin`, one true negative at 0.30. Its exclusion gives 165/199 accuracy (82.91%), a sensitivity result on the existing split. The fresh dataset screen found zero exact cross-split matches and 62 perceptual candidates. Contact-sheet review confirmed none. Exhaustive full-resolution review and an independent dataset evaluation are open. The 260-row optimized wrapper parity test verifies implementation parity on existing tensors. The two labeled upload fixtures are system acceptance cases.

[Dataset evidence and scripts](../evidence/dataset/) · [Wrapper parity](../evidence/pi-vision-parity.log) · [Independent procedure](INDEPENDENT-VALIDATION.md)
