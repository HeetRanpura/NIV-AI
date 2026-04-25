"""
Bias Detection Layer for NIV AI.

Compares LLM-generated verdict against deterministic financial state.
Detects when narrative reasoning diverges from hard mathematical facts.
This is the literal implementation of "Unbiased AI" — we audit our
own AI for systematic bias in real time.

Bias types detected:
  purchase_optimism: LLM says safe, math says stressed/critical
  overconfidence:    High LLM confidence despite failing stress tests
  minor_divergence:  Small misalignment, borderline case
  over_pessimism:    LLM more cautious than math warrants (rare)
  none:              LLM and deterministic analysis are aligned

Bias score 0-100:
  0-20:   No significant bias
  21-40:  Minor divergence
  41-60:  Moderate bias — display caution
  61-80:  Significant bias — override display
  81-100: Critical bias — verdict corrected
"""
from __future__ import annotations

# Mapping of LLM verdicts to numeric severity (higher = more optimistic/safe)
_VERDICT_SEVERITY: dict[str, int] = {
    "safe": 2,
    "reconsider": 1,
    "risky": 0,
}

# Mapping of deterministic states to numeric severity (higher = more stable/safe)
_STATE_SEVERITY: dict[str, int] = {
    "Stable": 3,
    "Strained": 2,
    "Fragile": 1,
    "Critical": 0,
}

# Display metadata per bias type
_BIAS_DISPLAY: dict[str, dict] = {
    "purchase_optimism": {
        "label": "AI Optimism Bias Detected",
        "color": "red",
        "description": (
            "The AI verdict is more optimistic than the mathematical analysis supports. "
            "Deterministic calculations indicate financial stress that the narrative may be downplaying."
        ),
    },
    "overconfidence": {
        "label": "Overconfidence Bias Detected",
        "color": "orange",
        "description": (
            "The AI expressed high confidence despite failing multiple stress tests. "
            "Confidence is not supported by the underlying financial resilience metrics."
        ),
    },
    "minor_divergence": {
        "label": "Minor Divergence",
        "color": "yellow",
        "description": (
            "Small misalignment between AI verdict and mathematical analysis. "
            "Borderline case — treat as a cautionary signal."
        ),
    },
    "over_pessimism": {
        "label": "Over-Pessimism Detected",
        "color": "blue",
        "description": (
            "The AI is more cautious than the math warrants. "
            "Financial metrics indicate a stronger position than the narrative suggests."
        ),
    },
    "none": {
        "label": "Analysis Aligned",
        "color": "green",
        "description": "AI verdict and deterministic analysis are in agreement.",
    },
}

# Integrity score bands
_INTEGRITY_BANDS = [
    (80, "High Integrity"),
    (60, "Moderate Integrity"),
    (40, "Integrity Concern"),
    (0,  "Low Integrity"),
]


def _corrected_verdict(deterministic_state: str) -> str:
    """Maps deterministic state back to the most appropriate LLM-style verdict."""
    mapping = {
        "Stable": "safe",
        "Strained": "reconsider",
        "Fragile": "risky",
        "Critical": "risky",
    }
    return mapping.get(deterministic_state, "reconsider")


def detect_verdict_bias(
    llm_verdict: str,
    llm_confidence_score: int,
    deterministic_state: str,
    deterministic_confidence: dict,
    stress_passed: int,
    stress_total: int,
) -> dict:
    """
    Detects misalignment between LLM verdict and deterministic financial state.

    Bias score 0-100:
      0-20:   No significant bias
      21-40:  Minor divergence
      41-60:  Moderate bias — display caution
      61-80:  Significant bias — override display
      81-100: Critical bias — verdict corrected

    Bias detection rules (evaluated in priority order):
      1. purchase_optimism:  LLM safe + det_state Fragile or Critical
      2. overconfidence:     confidence >= 7 + stress_passed < 50% of total
      3. minor_divergence:   LLM safe + det_state Strained
      4. over_pessimism:     LLM reconsider/risky + det_state Stable + all stress passed

    Args:
        llm_verdict:            "safe" | "reconsider" | "risky"
        llm_confidence_score:   1-10 confidence reported by the LLM
        deterministic_state:    "Stable" | "Strained" | "Fragile" | "Critical"
        deterministic_confidence: Confidence scoring dict (unused currently, reserved)
        stress_passed:          Number of stress scenarios the user can survive
        stress_total:           Total number of stress scenarios evaluated

    Returns:
        Dict with:
          bias_score (0-100)
          bias_type: "none" | "purchase_optimism" | "overconfidence" |
                     "minor_divergence" | "over_pessimism"
          bias_explanation: plain English explanation
          corrected_verdict: suggested corrected verdict if bias detected
          verdict_was_corrected: bool
          integrity_score: 100 - bias_score
          display_label: short label for UI
          display_color: "green" | "yellow" | "orange" | "red" | "blue"
          llm_verdict: original LLM verdict (echoed)
          deterministic_state: deterministic state (echoed)
          alignment_gap: int difference between verdict severity and state severity
    """
    llm_verdict_norm = (llm_verdict or "reconsider").lower().strip()
    det_state_norm = deterministic_state or "Strained"

    llm_sev = _VERDICT_SEVERITY.get(llm_verdict_norm, 1)
    det_sev = _STATE_SEVERITY.get(det_state_norm, 1)

    # Alignment gap: positive means LLM is more optimistic than math
    alignment_gap = llm_sev - (det_sev - 1)  # normalise det_sev to same 0-2 scale

    stress_ratio = stress_passed / stress_total if stress_total > 0 else 0.0

    # --- Rule evaluation (first match wins) ---

    # Rule 1: purchase_optimism — LLM says safe but math says Fragile/Critical
    if llm_verdict_norm == "safe" and det_state_norm in ("Fragile", "Critical"):
        if det_state_norm == "Critical":
            bias_score = 85
        else:
            bias_score = 68
        bias_type = "purchase_optimism"
        bias_explanation = (
            f"AI verdict is 'safe' but deterministic analysis classifies the financial state as "
            f"'{det_state_norm}'. EMI ratios, runway, and stress tests indicate significant stress "
            f"that the AI narrative is not adequately reflecting."
        )

    # Rule 2: overconfidence — high confidence + failing most stress tests
    elif llm_confidence_score >= 7 and stress_ratio < 0.50 and stress_total > 0:
        bias_score = 55
        bias_type = "overconfidence"
        bias_explanation = (
            f"AI expressed confidence score {llm_confidence_score}/10 but only "
            f"{stress_passed}/{stress_total} stress scenarios pass. High confidence is not "
            f"supported by stress resilience metrics."
        )

    # Rule 3: minor_divergence — LLM safe but math says Strained
    elif llm_verdict_norm == "safe" and det_state_norm == "Strained":
        bias_score = 30
        bias_type = "minor_divergence"
        bias_explanation = (
            f"AI verdict is 'safe' but deterministic analysis classifies the state as 'Strained'. "
            f"Financial metrics are at or slightly above safe thresholds — borderline case."
        )

    # Rule 4: over_pessimism — LLM cautious but math says Stable and all tests pass
    elif (
        llm_verdict_norm in ("reconsider", "risky")
        and det_state_norm == "Stable"
        and stress_total > 0
        and stress_passed == stress_total
    ):
        bias_score = 25
        bias_type = "over_pessimism"
        bias_explanation = (
            f"AI verdict is '{llm_verdict_norm}' but deterministic analysis shows financial state "
            f"is 'Stable' with all {stress_total} stress scenarios passing. The AI may be applying "
            f"excessive caution not supported by the numbers."
        )

    else:
        bias_score = 0
        bias_type = "none"
        bias_explanation = (
            f"AI verdict '{llm_verdict_norm}' aligns with deterministic state '{det_state_norm}'. "
            f"No systematic bias detected."
        )

    # Determine if verdict should be corrected
    verdict_was_corrected = bias_score >= 61 and bias_type not in ("none", "over_pessimism")
    corrected = _corrected_verdict(det_state_norm) if verdict_was_corrected else llm_verdict_norm

    integrity_score = max(100 - bias_score, 0)

    integrity_label = "Low Integrity"
    for threshold, label in _INTEGRITY_BANDS:
        if integrity_score >= threshold:
            integrity_label = label
            break

    display_meta = _BIAS_DISPLAY.get(bias_type, _BIAS_DISPLAY["none"])

    return {
        "bias_score": bias_score,
        "bias_type": bias_type,
        "bias_explanation": bias_explanation,
        "corrected_verdict": corrected,
        "verdict_was_corrected": verdict_was_corrected,
        "integrity_score": integrity_score,
        "integrity_label": integrity_label,
        "display_label": display_meta["label"],
        "display_color": display_meta["color"],
        "display_description": display_meta["description"],
        "llm_verdict": llm_verdict_norm,
        "deterministic_state": det_state_norm,
        "alignment_gap": alignment_gap,
        "stress_pass_rate": round(stress_ratio, 3),
        "llm_confidence_score": llm_confidence_score,
    }
