"""Compute defect detection metrics from the Pi vision batch CSVs."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean


def measure(path, threshold):
    with path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    labels = Counter(row["true_label"] for row in rows)
    if set(labels) != {"normal", "defective"}:
        raise ValueError(f"Unexpected labels in {path}")
    counts = Counter(
        (row["true_label"] == "defective", float(row["defective_probability"]) >= threshold)
        for row in rows
    )
    tp, fn = counts[True, True], counts[True, False]
    tn, fp = counts[False, False], counts[False, True]
    return {
        "threshold": threshold, "images": len(rows),
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "accuracy": (tp + tn) / len(rows),
        "defect_recall": tp / (tp + fn),
        "defect_precision": tp / (tp + fp) if tp + fp else 0,
        "f2": 5 * tp / (5 * tp + 4 * fn + fp),
        "mean_forward_ms": mean(float(row["inference_ms"]) for row in rows),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path)
    parser.add_argument("--threshold", nargs="+", type=float, default=[0.30, 0.35])
    args = parser.parse_args()
    report = {path.name: [measure(path, score) for score in args.threshold] for path in args.csv}
    print(json.dumps(report, indent=2))
