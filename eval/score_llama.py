#!/usr/bin/env python3
"""Score approved-check scenarios with the deterministic baseline and optional Pi runner."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from pipeline import advisory_prompt, rule_baseline_check_id, PROMPT_CHECKS, ASSISTANT_HEADER

MODEL = "pillguard_llama32_1b_q4_xnnpack.pte"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-runner", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--out", type=Path, default=Path("llama-score.txt"))
    args = parser.parse_args()
    scenarios = json.loads((ROOT / "eval/llama_scenarios.json").read_text())
    if any((args.llama_runner, args.model, args.tokenizer)) and not all((args.llama_runner, args.model, args.tokenizer)):
        parser.error("--llama-runner, --model, and --tokenizer must be provided together")
    rows = []
    for scenario in scenarios:
        history = scenario["history"][:10]
        last10 = sum(x == "FAIL" for x in history)
        last3 = sum(x == "FAIL" for x in history[:3])
        baseline = rule_baseline_check_id(scenario["decision"], last10)
        llama, latency = "—", "—"
        if args.llama_runner:
            prompt = advisory_prompt(scenario["decision"], scenario["probability"], last10, last3, scenario["shift_note"])
            started = time.monotonic()
            result = subprocess.run([str(args.llama_runner), "--model_path", str(args.model), "--tokenizer_path", str(args.tokenizer), "--prompt", prompt, "--temperature", "0", "--cpu_threads", "4", "--max_new_tokens", "3"], capture_output=True, text=True, timeout=90)
            latency = f"{time.monotonic()-started:.2f}s"
            if result.returncode == 0:
                _, marker, generation = result.stdout.rpartition(ASSISTANT_HEADER)
                if marker:
                    raw = re.split(r"<\|(?:eot_id|end_of_text)\|>", generation, maxsplit=1)[0]
                    found = re.search(r"[0-9]", raw)
                    if found and int(found.group()) in PROMPT_CHECKS:
                        llama = found.group()
                    else:
                        llama = "fallback"
                else:
                    llama = "fallback"
            else:
                llama = "fallback"
        rows.append((scenario["name"], scenario["expected_check_id"], baseline, llama, latency))
    table = "scenario | expected | baseline | Llama | latency\n" + "--- | ---: | ---: | ---: | ---\n" + "\n".join("%s | %s | %s | %s | %s" % row for row in rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table + "\n")
    print(table)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
