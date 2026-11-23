"""Run the installed Pi vision and Llama executables sequentially."""
import json
import math
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from pillguard_safety_guard import build_result

VISION_MODEL = "pillguard_efficientnetv2_s_experiment2_xnnpack.pte"
LLAMA_MODEL = "pillguard_llama32_1b_q4_xnnpack.pte"
THRESHOLD = 0.30
ASSISTANT_HEADER = "<|start_header_id|>assistant<|end_header_id|>"
APPROVED_CHECKS = {
    1: "Continue standard QC review. No pattern in recent results.",
    2: "Re-inspect this tablet by hand under the bench lamp and confirm the defect.",
    3: "Inspect punch and die tooling for wear or chipping.",
    4: "Check the granulate or feed lot for contamination, moisture or foreign particles.",
    5: "Check camera, lighting and lens, and re-run a known-good reference tablet before trusting results.",
}
PROMPT_CHECKS = {
    1: "continue standard QC",
    2: "hand re-inspect tablet",
    3: "inspect punch and die",
    4: "check granulate or feed lot",
    5: "check camera and reference tablet",
}
PROMPT_MAX_CHARS = 700
EXPLANATIONS = {"defective": "", "normal": ""}


def rule_baseline_check_id(decision, last10_fails):
    if decision == "FAIL" and last10_fails >= 3:
        return 5
    if decision == "FAIL":
        return 2
    if last10_fails <= 1:
        return 1
    return 5


def advisory_prompt(decision, probability_defective, last10_fails, last3_fails, shift_note):
    # Operator text must not be able to inject chat-template tokens.
    note = re.sub(r"<\|[^|]*\|>", "", (shift_note or "")).replace("<|", "").replace("|>", "")
    note = " ".join(note.split())[:160]
    prompt = (
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        f"Result {decision}; defect probability {probability_defective:.2f}. "
        f"Recent FAIL: {last10_fails}/10, {last3_fails}/3. Shift note: {note or '(none)'}.\n"
        "Choose one check; reply with its number only.\n"
        + "\n".join(f"{i}. {text}" for i, text in PROMPT_CHECKS.items())
        + "<|eot_id|>" + ASSISTANT_HEADER + "\n\n"
    )
    if len(prompt) > PROMPT_MAX_CHARS:
        raise ValueError("Advisory prompt exceeds character limit")
    return prompt


def field(output, label):
    match = re.search(rf"^{re.escape(label)}: (.+)$", output, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Vision runner did not report {label}")
    return match.group(1)


def qc_result(output):
    defective = float(field(output, "Defective probability"))
    normal = float(field(output, "Normal probability"))
    threshold = float(field(output, "Threshold"))
    latency = float(field(output, "Forward latency").removesuffix(" ms"))
    if (
        not (0 <= defective <= 1 and 0 <= normal <= 1)
        or not math.isclose(defective + normal, 1, abs_tol=0.000002)
        or not math.isfinite(latency)
        or latency < 0
        or threshold != THRESHOLD
    ):
        raise RuntimeError("Invalid Experiment 2 output or unexpected threshold")
    # The executable compares full-precision probabilities and prints rounded
    # values. Use its decision at the threshold if the two can differ by rounding.
    prediction = field(output, "Prediction").lower()
    if prediction not in EXPLANATIONS or (
        abs(defective - threshold) > 0.0000005
        and (prediction == "defective") != (defective >= threshold)
    ):
        raise RuntimeError("Experiment 2 decision disagrees with its score")
    confidence = defective if prediction == "defective" else normal
    safety = build_result(prediction, confidence, "NOT_ASSESSED")
    return {
        "vision_model": VISION_MODEL,
        "vision_forward_ms": latency,
        "classification": prediction,
        "model_score": confidence,
        "probability_defective": defective,
        "probability_normal": normal,
        "threshold": threshold,
        "screening_decision": "FAIL" if prediction == "defective" else "PASS",
        "required_action": safety["required_action"],
        "advisory": safety["display_advisory"],
        "severity": safety["severity"],
        "dispensing_authorized": safety["dispensing_authorized"],
    }


def approved_advisory(raw, classification):
    expected = EXPLANATIONS[classification]
    normalized = " ".join(raw.split())
    # Accept only the complete, grounded sentence for this classification.
    return normalized if normalized.casefold() == expected.casefold() else ""


class Pipeline:
    def __init__(self, vision_dir, llama_runner, tokenizer):
        self.vision_dir = Path(vision_dir).resolve()
        self.llama_runner = Path(llama_runner).resolve()
        self.tokenizer = Path(tokenizer).resolve()
        self.lock = threading.Lock()

    def inspect(self, image):
        with self.lock:
            start = time.monotonic()
            process = subprocess.run(
                [sys.executable, "run_pillguard.py", str(Path(image).resolve())],
                cwd=self.vision_dir, capture_output=True, text=True, timeout=30,
            )
            if process.returncode:
                raise RuntimeError("Experiment 2 inference failed: " + process.stderr[-400:])
            result = qc_result(process.stdout)
            result["vision_wall_s"] = round(time.monotonic() - start, 3)
            return result

    def advisory(self, decision, probability_defective=0.0, last10_fails=0,
                 last3_fails=0, shift_note=""):
        return self._advisory(decision, probability_defective, last10_fails,
                              last3_fails, shift_note)

    def _advisory(self, decision, probability_defective, last10_fails, last3_fails, shift_note):
        start = time.monotonic()
        status, raw, metrics = "ERROR", "", {}
        baseline = rule_baseline_check_id(decision, last10_fails)
        selected = None
        prompt = advisory_prompt(decision, probability_defective, last10_fails, last3_fails, shift_note)
        try:
            process = subprocess.run(
                [
                    self.llama_runner, "--model_path", self.vision_dir / LLAMA_MODEL,
                    "--tokenizer_path", self.tokenizer, "--prompt", prompt,
                    "--temperature", "0", "--cpu_threads", "4", "--max_new_tokens", "3",
                ],
                capture_output=True, text=True, timeout=90,
            )
            if process.returncode:
                raw = f"Runner exit {process.returncode}. {process.stderr[-500:]}"
            else:
                _, marker, generation = process.stdout.rpartition(ASSISTANT_HEADER)
                raw, report_marker, report = generation.rpartition("\nPyTorchObserver ")
                if not marker or not report_marker:
                    raise ValueError("Missing Llama generation or timing report")
                metrics = json.loads(report.strip())
                raw = re.split(r"<\|(?:eot_id|end_of_text)\|>", raw, maxsplit=1)[0].strip()
                match = re.search(r"[0-9]", raw)
                if match:
                    candidate = int(match.group(0))
                    if candidate in APPROVED_CHECKS:
                        selected = candidate
                status = "COMPLETED_DISPLAYED" if selected is not None else "COMPLETED_NOT_APPROVED"
        except subprocess.TimeoutExpired:
            status, raw = "TIMEOUT", "Llama generation exceeded 90 seconds"
        except (OSError, ValueError) as exc:
            raw = str(exc)
        source = "llama" if selected is not None else "rule_fallback"
        chosen = selected if selected is not None else baseline
        return {
            "llama_model": LLAMA_MODEL,
            "llama_status": status,
            "llama_explanation": APPROVED_CHECKS[chosen],
            "advisory_check_id": chosen,
            "advisory_check_text": APPROVED_CHECKS[chosen],
            "advisory_source": source,
            "rule_baseline_check_id": baseline,
            "llama_raw_for_review": raw[-1200:],
            "llama_metrics": metrics,
            "llama_latency_s": round(time.monotonic() - start, 3),
        }
