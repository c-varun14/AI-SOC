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
EXPLANATIONS = {
    "defective": "The tablet was flagged as defective and should be quarantined for quality review.",
    "normal": "The tablet was classified as normal and should continue to standard quality review.",
}


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
            result.update(self._advisory(result["classification"]))
            return result

    def _advisory(self, classification):
        start = time.monotonic()
        status, approved, raw, metrics = "ERROR", "", "", {}
        prompt = (
            "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
            "Copy exactly:\n"
            + EXPLANATIONS[classification]
            + "<|eot_id|>" + ASSISTANT_HEADER + "\n\n"
        )
        try:
            process = subprocess.run(
                [
                    self.llama_runner, "--model_path", self.vision_dir / LLAMA_MODEL,
                    "--tokenizer_path", self.tokenizer, "--prompt", prompt,
                    "--temperature", "0", "--cpu_threads", "4", "--max_new_tokens", "24",
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
                approved = approved_advisory(raw, classification)
                status = "COMPLETED_DISPLAYED" if approved else "COMPLETED_NOT_APPROVED"
        except subprocess.TimeoutExpired:
            status, raw = "TIMEOUT", "Llama generation exceeded 90 seconds"
        except (OSError, ValueError) as exc:
            raw = str(exc)
        return {
            "llama_model": LLAMA_MODEL,
            "llama_status": status,
            "llama_explanation": approved,
            "llama_raw_for_review": raw[-1200:],
            "llama_metrics": metrics,
            "llama_latency_s": round(time.monotonic() - start, 3),
        }
