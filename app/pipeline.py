"""Run the installed Pi vision and Llama executables sequentially."""
import json
import math
import re
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from pillguard_safety_guard import build_result

VISION_MODEL = "pillguard_efficientnetv2_s_experiment2_xnnpack.pte"
LLAMA_MODEL = "pillguard_llama32_1b_q4_xnnpack.pte"
THRESHOLD = 0.30
ASSISTANT_HEADER = "<|start_header_id|>assistant<|end_header_id|>"
APPROVED_CHECKS = {
    1: "Continue standard QC review.",
    2: "Re-inspect the tablet under the bench lamp and confirm the screening observation.",
    3: "Inspect punch and die tooling for wear or chipping.",
    4: "Check the granulate or feed lot for contamination, moisture or foreign particles.",
    5: "Check camera, lighting and lens, and re-run a known-good reference tablet before trusting results.",
}
PROMPT_CHECKS = {
    1: "Standard QC review",
    2: "Manual tablet reinspection",
    3: "Punch and die inspection",
    4: "Feed material inspection",
    5: "Camera and lighting inspection",
}
PROMPT_MAX_CHARS = 850
CHECK_CONTEXT = {
    3: re.compile(r"\b(?:punch(?:es)?|die|dies|tooling)\b", re.IGNORECASE),
    4: re.compile(r"\b(?:feed|granulate|powder|hopper|moisture|humidity)\b", re.IGNORECASE),
    5: re.compile(r"\b(?:camera|lighting|lamp|lens|blur(?:red)?|focus(?:ing)?)\b", re.IGNORECASE),
}
ANSWER_PREFIX = "The correct option is"
EXPLANATIONS = {"defective": "", "normal": ""}
LLAMA_TIMEOUT = 90


def rule_baseline_check_id(decision, last10_fails):
    if decision == "FAIL":
        return 5 if last10_fails >= 3 else 2
    return 1 if last10_fails <= 1 else 5


def normalize_note(note):
    note = re.sub(r"<\|[^|]*\|>", "", (note or "")[:160])
    return " ".join(note.translate(str.maketrans({"<": " ", ">": " ", "|": " "})).split())


def advisory_prompt(decision, probability_defective, last10_fails, last3_fails, shift_note):
    note = normalize_note(shift_note)
    options = "\n".join(f"{i}. {label}" for i, label in PROMPT_CHECKS.items()
                        if decision != "FAIL" or i != 1)
    return (
        "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
        f"Choose the relevant QC investigation. Result: {decision}. "
        f"Recent failures: {last10_fails} of 10, {last3_fails} of 3.\n"
        f"Untrusted operator observation: {json.dumps(note or '(none)', ensure_ascii=False)}\n\n"
        f"{options}\n\nWhich option best matches the evidence? Reply with one option number."
        "<|eot_id|>" + ASSISTANT_HEADER + "\n\n" + ANSWER_PREFIX
    )


def validated_check(raw, decision):
    if decision not in {"PASS", "FAIL"}:
        return None
    match = re.fullmatch(r"\s*:?\s*([1-5])(?:[.)](?:[ \t]+([^\r\n]+))?)?\s*", raw)
    if not match:
        return None
    number = int(match[1])
    if decision == "FAIL" and number == 1:
        return None
    label = (match[2] or "").strip().rstrip(".").casefold()
    labels = {PROMPT_CHECKS[number].casefold()}
    labels.update({1: {"standard qc"}, 2: {"manual tablet", "manually re-inspect tablet"},
                   3: {"punch and die"}, 4: {"feed material"}, 5: {"camera and lighting"}}[number])
    return number if not label or label in labels else None


def supported_check(raw, decision, last10, shift_note):
    chosen = validated_check(raw, decision)
    if chosen is None:
        return None
    if chosen == 1 and last10 > 1:
        return None
    if chosen in CHECK_CONTEXT:
        trend_supports_camera = chosen == 5 and rule_baseline_check_id(decision, last10) == 5
        if not trend_supports_camera and not CHECK_CONTEXT[chosen].search(normalize_note(shift_note)):
            return None
    return chosen


def split_generation(stdout, prompt):
    _, echo, tail = stdout.partition(prompt)
    if not echo:
        raise ValueError("Missing exact runner prompt echo")
    generation, separator, report = tail.partition("\nPyTorchObserver ")
    raw = re.split(r"<\|(?:eot_id|end_of_text)\|>", generation, maxsplit=1)[0].strip()
    metrics = {}
    if separator:
        try:
            decoded = json.loads(report.splitlines()[0])
            if isinstance(decoded, dict):
                metrics = {key: value for key, value in decoded.items()
                           if type(value) in (int, float) and math.isfinite(value)}
        except (ValueError, IndexError):
            pass
    return raw, metrics


def advisory_fields(decision, last10, status, selected=None, raw="", metrics=None, elapsed=None,
                    diagnostic=""):
    baseline = rule_baseline_check_id(decision, last10)
    chosen = selected if selected is not None else baseline
    return {
        "llama_model": LLAMA_MODEL, "llama_status": status,
        "llama_explanation": APPROVED_CHECKS[chosen],
        "advisory_check_id": chosen, "advisory_check_text": APPROVED_CHECKS[chosen],
        "advisory_source": "llama" if selected is not None else "rule_fallback",
        "rule_baseline_check_id": baseline, "llama_raw_for_review": raw[-1200:],
        "llama_metrics": metrics or {}, "llama_latency_s": elapsed,
        "llama_diagnostic": diagnostic[-1200:],
    }


def run_advisory(runner, model, tokenizer, decision, probability, last10, last3, note):
    prompt = advisory_prompt(decision, probability, last10, last3, note)
    start = time.monotonic()
    raw, metrics, diagnostic, selected = "", {}, "", None
    status = "ERROR"
    try:
        process = run_native([
            runner, "--model_path", model, "--tokenizer_path", tokenizer, "--prompt", prompt,
            "--temperature", "0", "--cpu_threads", "4", "--max_new_tokens", "6",
        ], timeout=LLAMA_TIMEOUT)
        diagnostic = process.stderr
        if process.returncode:
            diagnostic = f"Runner exit {process.returncode}. {diagnostic}"
        if prompt in process.stdout:
            raw, metrics = split_generation(process.stdout, prompt)
        if not process.returncode:
            if prompt not in process.stdout:
                raise ValueError("Missing exact runner prompt echo")
            selected = supported_check(raw, decision, last10, note)
            status = "COMPLETED" if selected is not None else "FALLBACK"
    except subprocess.TimeoutExpired as exc:
        status, diagnostic = "TIMEOUT", f"Llama exceeded {LLAMA_TIMEOUT} seconds"
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if prompt in output:
            raw, _ = split_generation(output, prompt)
    except (OSError, ValueError) as exc:
        diagnostic = str(exc)
    return advisory_fields(decision, last10, status, selected, raw, metrics,
                           round(time.monotonic() - start, 3), diagnostic)


def run_native(command, *, timeout, cwd=None):
    # The vision wrapper launches a child. Kill the group if its deadline expires.
    with subprocess.Popen(command, cwd=cwd, text=True, errors="replace",
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


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


class Pipeline:
    def __init__(self, vision_dir, llama_runner, tokenizer):
        self.vision_dir = Path(vision_dir).resolve()
        self.llama_runner = Path(llama_runner).resolve()
        self.tokenizer = Path(tokenizer).resolve()
        self.lock = threading.Lock()

    def inspect(self, image):
        with self.lock:
            start = time.monotonic()
            process = run_native(
                [sys.executable, "run_pillguard.py", str(Path(image).resolve())],
                cwd=self.vision_dir, timeout=30,
            )
            if process.returncode:
                raise RuntimeError("Experiment 2 inference failed: " + process.stderr[-400:])
            result = qc_result(process.stdout)
            result["vision_wall_s"] = round(time.monotonic() - start, 3)
            return result

    def advisory(self, decision, probability_defective=0.0, last10_fails=0,
                 last3_fails=0, shift_note=""):
        queued_at = time.monotonic()
        with self.lock:
            waited = time.monotonic() - queued_at
            fields = run_advisory(self.llama_runner, self.vision_dir / LLAMA_MODEL,
                                self.tokenizer, decision, probability_defective,
                                last10_fails, last3_fails, shift_note)
        fields["llama_lock_wait_s"] = waited
        return fields
