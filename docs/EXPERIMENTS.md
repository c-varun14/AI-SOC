# Phase 1 experiments

## Llama advisory evaluation

The earlier UI-review build accepted 1 of 6 team-reported Pi inspections. The accepted answer recommended continuing standard QC on a FAIL. Five fell back. Four verdicts arrived in under two seconds. These were actual inspection inputs, distinct from the advisory evaluation scenarios. [Reported six](../evidence/phase1-rc/prior-six-reported.json)

Both native prompt runs used the existing Llama 3.2 1B Q4 model, original tokenizer, four CPU threads, temperature zero and the same 12 development plus four held-out scenarios. Each run executed one process at a time. The 12 seeded development scenarios were available during prompt design. The four additional test scenarios were excluded from the prompt and have limited coverage. The final context gate was selected after reviewing the initial run, so its replay is a retrospective evaluation.

| Configuration | Gate accepted | Fallback | Choices matching expected, including fallback | Verdict-consistent displayed choices | Median runner wall time |
|---|---:|---:|---:|---:|---:|
| Rules recomputed from code | — | — | 7/12 development, 1/4 held out | 16/16 | — |
| Pi answer prefix, 6 tokens, structural gate | 13/16 | 3/16 | 5/12, 1/4 | 16/16 | 19.15 s |
| Pi short labels and extra instructions, 8 tokens | 0/16 | 16/16 | 7/12, 1/4 | 16/16 | 23.61 s |
| Released prefix plus context gate, replay of Pi output | 5/16 | 11/16 | 8/12, 1/4 | 16/16 | 19.15 s inherited |

The prefix-only run returned frequent tooling answers without evidence in the operator note. The short-label run often echoed and truncated an option description. For the RC, option 1 requires PASS and a stable history. Tooling and feed checks require a related observation. A camera check requires a related observation or a deterministic trend trigger. Each accepted result matched its expected label in this small replay (4 development, 1 held out). The production gate and deterministic fallback improved the development count by one relative to rules alone. Held-out agreement stayed at 1/4. The results do not establish that Llama outperforms the rules.

The inference runner logs an HF JSON parsing warning for the existing tokenizer. ExecuTorch 1.6.0's `load_tokenizer` tries the HF JSON loader before alternative formats, including Tiktoken. The runs completed with generated tokens and observer timings. The diagnostics identify the warning and show successful execution, although the diagnostic excerpts do not independently identify the exact successful loader. The model, tokenizer and executable were reused as deployed. [Local source location in upstream v1.6.0](https://github.com/pytorch/executorch/blob/v1.6.0/extension/llm/runner/llm_runner_helper.cpp)

Machine-readable records include the raw generated text, fallback status, exact choice, execution seconds and available observer telemetry. [Deterministic baseline](../evidence/phase1-rc/llama-baseline.json) · [Six-token first run](../evidence/phase1-rc/pi-llama-prefix.json) · [Eight-token comparison](../evidence/phase1-rc/pi-llama-short-label.json) · [Production validator replay](../evidence/phase1-rc/production-replay.json)

## Vision and resource scope

Phase 1 retains the evaluated FP32 model, XNNPACK and 0.30 threshold. The archived dataset evaluation and the current serialized Pi run are described in the [technical report](TECHNICAL-REPORT.md) and [release handoff](PHASE1-RELEASE.md). INT8, the thread sweep, defect-area measurement and validated severity are deferred.
