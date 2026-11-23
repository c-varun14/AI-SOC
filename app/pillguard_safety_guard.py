"""Independent PillGuard inspection safety guard."""

def build_result(classification, confidence, issue, llama_text=""):
    classification = classification.lower().strip()

    if classification not in ("defective", "normal"):
        raise ValueError("Unknown classification")

    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1")

    if classification == "defective":
        action = "QUARANTINE"
        advisory = (
            "Potentially defective tablet. "
            "Quarantine for quality review. "
            "Do not dispense."
        )
    else:
        action = "STANDARD_QC_REVIEW"
        advisory = (
            "No defect predicted by the model. "
            "Follow standard quality-control procedures. "
            "This prediction is not authorization to dispense."
        )

    return {
        "classification": classification,
        "confidence": confidence,
        "reported_issue": issue,
        "severity": "NOT_ASSESSED",
        "required_action": action,
        "dispensing_authorized": False,
        "display_advisory": advisory,
        "llama_raw_for_review": llama_text,
        "llama_approved_for_display": False,
    }


if __name__ == "__main__":
    examples = {
        "mixed_precision": (
            "I, a tablet, am showing signs of wear. "
            "I am required to be quarant"
        ),
        "eight_bit": (
            "Defective tablet with visible crack. "
            "Quarantine for quality review to ensure safe "
            "handling and prevent potential data loss."
        ),
    }

    print("=== STEP 303: SAFETY GUARD TEST ===")

    for model_name, generated_text in examples.items():
        result = build_result(
            classification="defective",
            confidence=0.80,
            issue="visible crack",
            llama_text=generated_text,
        )

        print("\nModel:", model_name)
        print("Required action:", result["required_action"])
        print("Display advisory:", result["display_advisory"])
        print("Severity:", result["severity"])
        print("Llama approved:", result["llama_approved_for_display"])

        assert result["required_action"] == "QUARANTINE"
        assert result["dispensing_authorized"] is False
        assert "Do not dispense" in result["display_advisory"]
        assert "data loss" not in result["display_advisory"]

    print("\n=== ALL SAFETY GUARD TESTS PASSED ===")
    print("=== STEP 303 COMPLETE ===")
