# Model and runtime metadata

| Field | Experiment 2 vision | Advisory |
|---|---|---|
| Architecture | EfficientNetV2-S, binary classifier | Llama 3.2 1B Instruct |
| Deployed file | `pillguard_efficientnetv2_s_experiment2_xnnpack.pte` | `pillguard_llama32_1b_q4_xnnpack.pte` |
| Runtime | ARM64 C++ ExecuTorch 1.6.0, XNNPACK | ARM64 standalone ExecuTorch 1.6.0, XNNPACK |
| Export | Forward on float32 NCHW | 8da4w, group size 128, embedding quantization 4-bit with groups of 32, float32 override, KV cache, 256-token sequence/context settings |
| Decision / generation | Class order `defective=0, normal=1`. Defective if p(defective) ≥ 0.30 | Original tokenizer, greedy decoding, four CPU threads, up to 3 output tokens; selects one of five approved QC checks from result, recent SQLite trend and optional shift note |

Vision preprocessing decodes with Pillow, converts to RGB, resizes directly to 224 × 224 using bilinear interpolation, converts to float32 and divides by 255. RGB mean is `[0.485, 0.456, 0.406]`. Standard deviation is `[0.229, 0.224, 0.225]`. Data are transposed to contiguous CHW and the C++ input shape is `1 × 3 × 224 × 224`.

The saved training checkpoint metadata separately records `Train_augmented` and a validation selection threshold of 0.35. Runtime code and acceptance logs show 0.30 for deployment. A model probability is an uncalibrated score. Neither class probabilities nor Llama outputs establish defect subtype or severity.

The advisory prompt is bounded for the model's 256-token context. Only a first reply digit from 1–5 selects a check; invalid replies and runner failures display the deterministic rule baseline. Llama cannot alter the screening decision, required action, mandatory QC instruction or dispensing authorization. Llama accuracy on the seeded scenarios has not yet been measured on the Pi.

[Pi model, tokenizer and runtime hashes](../evidence/pi-sha256.txt) · [Optimized executable and prompt hashes](../evidence/verified-optimized.sha256) · [Llama export log](../evidence/llama-export.log)

## Export provenance

The repository includes a path-parameterized vision exporter. It requires the matching Experiment 2 checkpoint, a normalized sample tensor and the matching Torch, torchvision and ExecuTorch environment. From a separate working directory run `python models/export_efficientnetv2_experiment2_to_executorch.py --checkpoint <checkpoint> --sample <tensor> --output <new-file.pte>`. The output is created exclusively. Re-export is optional.

The historical Llama export used the existing CPU ExecuTorch 1.6.0 package, original Meta checkpoint files and tokenizer. In an empty output working directory with the required inputs, the archival recipe is:

```sh
OMP_NUM_THREADS=2 python -m executorch.examples.models.llama.export_llama \
  --model llama3_2 --checkpoint "$LLAMA_CHECKPOINT" --params "$LLAMA_PARAMS" \
  --tokenizer_path "$LLAMA_TOKENIZER" --quantization_mode 8da4w --group_size 128 \
  --embedding-quantize 4,32 --dtype-override fp32 --use_kv_cache \
  --max_seq_length 256 --max_context_length 256 --xnnpack \
  --metadata '{"get_bos_id":128000,"get_eos_ids":[128009,128001]}' \
  --output-dir . --output_name pillguard_llama32_1b_q4_xnnpack.pte
```

This repository does not include the model weights and does not retrain or re-export them during setup. [Cortex-A72 build recipe](../models/llama-build/README.md) · [Licensing and attribution](../notices/RIGHTS.md)
