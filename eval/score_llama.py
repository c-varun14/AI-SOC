#!/usr/bin/env python3
"""Measure the production prompt and validator, or score the deterministic baseline alone."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from pipeline import advisory_fields, advisory_prompt, rule_baseline_check_id, run_advisory, supported_check

HELD_OUT = [
    {"name": "changed-die", "decision": "FAIL", "probability": .77, "history": ["FAIL"] * 4,
     "shift_note": "Die exchanged at shift start", "expected_check_id": 3},
    {"name": "powder-clumps", "decision": "FAIL", "probability": .69, "history": ["FAIL"] * 2,
     "shift_note": "Powder clumps observed in hopper", "expected_check_id": 4},
    {"name": "blurred-reference", "decision": "FAIL", "probability": .64, "history": ["FAIL", "PASS"],
     "shift_note": "Known reference image suddenly blurred after refocusing", "expected_check_id": 5},
    {"name": "quiet-shift", "decision": "PASS", "probability": .06, "history": ["PASS"] * 8,
     "shift_note": "Operator signed the routine log", "expected_check_id": 1},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llama-runner", type=Path)
    parser.add_argument("--model", type=Path)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--out", type=Path, default=Path("llama-score.json"))
    parser.add_argument("--replay", type=Path, help="Apply the production gate to recorded, identical-prompt runs.")
    args = parser.parse_args()
    paths = (args.llama_runner, args.model, args.tokenizer)
    if any(paths) and not all(paths):
        parser.error("Supply all three native artifact paths together.")
    if args.replay and any(paths):
        parser.error("Use replay or the native runner separately.")
    recorded = {}
    if args.replay:
        recorded = {row["name"]: row for row in json.loads(args.replay.read_text())["rows"]}
    scenarios = json.loads((ROOT / "eval/llama_scenarios.json").read_text())
    rows = []
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def save():
        summary = {}
        for cohort in ("development", "held_out"):
            subset = [r for r in rows if r["cohort"] == cohort]
            actual = [r for r in subset if "live" in r]
            accepted = [r for r in actual if r["live"]["advisory_source"] == "llama"]
            summary[cohort] = {
                "cases": len(subset), "native_runs": len(actual),
                "baseline_agreement": sum(r["baseline_check_id"] == r["expected_check_id"] for r in subset),
                "accepted": len(accepted) if actual else None,
                "fallback": len(actual) - len(accepted) if actual else None,
                "accepted_expected_agreement": sum(r["live"]["advisory_check_id"] == r["expected_check_id"]
                                                    for r in accepted) if actual else None,
                "displayed_expected_agreement": sum(r["live"]["advisory_check_id"] == r["expected_check_id"]
                                                     for r in actual) if actual else None,
                "consistent_displayed": sum(r["decision"] != "FAIL" or r["live"]["advisory_check_id"] != 1
                                            for r in actual) if actual else None,
            }
        staged = args.out.with_suffix(".partial")
        staged.write_text(json.dumps({"mode": "replay" if args.replay else "native" if all(paths) else "baseline",
                                      "summary": summary, "rows": rows}, indent=2) + "\n")
        staged.replace(args.out)

    for index, case in enumerate(scenarios + HELD_OUT):
        history = case["history"][:10]
        last10, last3 = history.count("FAIL"), history[:3].count("FAIL")
        decision = case["decision"]
        row = {**case, "cohort": "development" if index < len(scenarios) else "held_out",
               "baseline_check_id": rule_baseline_check_id(decision, last10)}
        if all(paths) or args.replay:
            row["prompt"] = advisory_prompt(decision, case["probability"], last10, last3, case["shift_note"])
        if all(paths):
            row["live"] = run_advisory(*paths, decision, case["probability"], last10, last3, case["shift_note"])
        elif args.replay:
            original = recorded[case["name"]]
            if any(original[key] != case[key] for key in case):
                raise ValueError(f"Scenario mismatch for {case['name']}")
            if "prompt" in original and original["prompt"] != row["prompt"]:
                raise ValueError(f"Prompt mismatch for {case['name']}")
            prior = original["live"]
            raw = prior["llama_raw_for_review"]
            selected = supported_check(raw, decision, last10, case["shift_note"])
            status = prior["llama_status"]
            if status in {"ERROR", "TIMEOUT"}:
                selected = None
            else:
                status = "COMPLETED" if selected is not None else "FALLBACK"
            row["live"] = advisory_fields(
                decision, last10, status, selected, raw, prior["llama_metrics"],
                prior["llama_latency_s"], prior["llama_diagnostic"],
            )
        rows.append(row)
        save()
        print(case["name"], row.get("live", {}).get("llama_status", "baseline"), flush=True)


if __name__ == "__main__":
    main()
