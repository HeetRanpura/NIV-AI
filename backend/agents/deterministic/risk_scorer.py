"""
Risk Scoring Agent — Composite 0-100 score from four weighted components.
HIGHER score = SAFER. No AI. Entirely deterministic.

Components and weights:
  EMI ratio:         35 points  (35 if ratio < 0.25, scales to 0 at ratio 0.60)
  Buffer months:     25 points  (25 if buffer > 12 months, scales to 0 at 0 months)
  Scenario survival: 30 points  (6 points per survivable scenario, max 30)
  Tenure vs age:     10 points  (10 if loan ends before 55, scales to 0 if after 65)

Risk labels:
  Safe:          score >= 70
  Moderate Risk: score 40-69
  High Risk:     score < 40
"""
from schemas.schemas import (
    FinancialRealityOutput, AllScenariosOutput,
    RiskScoreOutput, RiskScoreComponentScores, RiskLabel
)


def calculate_risk_score(
    financial_reality: FinancialRealityOutput,
    all_scenarios: AllScenariosOutput,
    age: int,
    tenure_years: int,
) -> RiskScoreOutput:
    """
    Calculates composite risk score from 0 (worst) to 100 (best).
    Higher score = safer financial position.
    """
    risk_factors = []
    score_explanation = {}

    # ------------------------------------------------------------------
    # 1. EMI Ratio component (max 35 points)
    #    Score 35 if ratio <= 0.25, linearly drops to 0 at ratio 0.60
    # ------------------------------------------------------------------
    ratio = financial_reality.emi_to_income_ratio

    if ratio <= 0.25:
        emi_score = 35.0
        score_explanation["EMI Ratio"] = (
            f"Excellent — your EMI is only {ratio*100:.0f}% of income, well within comfort zone."
        )
    elif ratio >= 0.60:
        emi_score = 0.0
        risk_factors.append(f"Dangerously high EMI ratio at {ratio*100:.0f}% of income")
        score_explanation["EMI Ratio"] = (
            f"Critical — your EMI consumes {ratio*100:.0f}% of income, leaving almost nothing for life."
        )
    else:
        # Linear interpolation: 35 at 0.25, 0 at 0.60
        emi_score = 35.0 * (0.60 - ratio) / (0.60 - 0.25)
        if ratio > 0.45:
            risk_factors.append(f"High EMI ratio at {ratio*100:.0f}% of income")
        score_explanation["EMI Ratio"] = (
            f"Your EMI is {ratio*100:.0f}% of income. "
            f"{'This is getting stretched.' if ratio > 0.35 else 'This is manageable.'}"
        )

    # ------------------------------------------------------------------
    # 2. Buffer months component (max 25 points)
    #    Score 25 if buffer >= 12, linearly drops to 0 at buffer 0
    # ------------------------------------------------------------------
    buffer = all_scenarios.base_case.buffer_months

    if buffer >= 12:
        buffer_score = 25.0
        score_explanation["Savings Buffer"] = (
            f"Strong — you have {buffer} months of financial runway."
        )
    elif buffer <= 0:
        buffer_score = 0.0
        risk_factors.append("No savings buffer — finances are immediately underwater")
        score_explanation["Savings Buffer"] = (
            "Critical — you have no savings runway at all."
        )
    else:
        buffer_score = 25.0 * (buffer / 12.0)
        if buffer < 6:
            risk_factors.append(f"Low savings buffer of only {buffer} months")
        score_explanation["Savings Buffer"] = (
            f"Your {buffer}-month buffer provides {'limited' if buffer < 6 else 'moderate'} protection."
        )

    # ------------------------------------------------------------------
    # 3. Scenario survival component (max 30 points)
    #    6 points per survivable scenario (out of 5 scenarios = max 30)
    # ------------------------------------------------------------------
    survived = all_scenarios.scenarios_survived
    scenario_score = survived * 6.0

    all_five = [
        all_scenarios.base_case,
        all_scenarios.income_drop_30pct,
        all_scenarios.job_loss_6_months,
        all_scenarios.interest_rate_hike_2pct,
        all_scenarios.emergency_expense_5L,
    ]
    failed_names = [s.scenario_name for s in all_five if not s.survivable]

    if survived == 5:
        score_explanation["Stress Tests"] = (
            "Excellent — you survive all 5 financial stress scenarios."
        )
    else:
        risk_factors.append(
            f"Failed {5 - survived} of 5 stress scenarios: {', '.join(failed_names)}"
        )
        score_explanation["Stress Tests"] = (
            f"You survive {survived}/5 scenarios. "
            f"Vulnerable to: {', '.join(failed_names)}."
        )

    # ------------------------------------------------------------------
    # 4. Tenure vs Age component (max 10 points)
    #    Score 10 if loan ends before age 55
    #    Scales linearly to 0 if loan ends after age 65
    # ------------------------------------------------------------------
    loan_end_age = age + tenure_years

    if loan_end_age <= 55:
        tenure_score = 10.0
        score_explanation["Tenure vs Age"] = (
            f"Good — your loan ends at age {loan_end_age}, well before retirement."
        )
    elif loan_end_age >= 65:
        tenure_score = 0.0
        risk_factors.append(f"Loan extends to age {loan_end_age}, past typical retirement")
        score_explanation["Tenure vs Age"] = (
            f"Risky — your loan ends at age {loan_end_age}, extending past retirement."
        )
    else:
        # Linear: 10 at age 55, 0 at age 65
        tenure_score = 10.0 * (65 - loan_end_age) / 10.0
        if loan_end_age > 60:
            risk_factors.append(f"Loan extends to age {loan_end_age}, close to retirement")
        score_explanation["Tenure vs Age"] = (
            f"Your loan ends at age {loan_end_age}. "
            f"{'Consider a shorter tenure.' if loan_end_age > 58 else 'Reasonable timeline.'}"
        )

    # ------------------------------------------------------------------
    # Composite score
    # ------------------------------------------------------------------
    composite = round(emi_score + buffer_score + scenario_score + tenure_score, 1)
    composite = max(0.0, min(100.0, composite))

    if composite >= 70:
        risk_label = RiskLabel.SAFE
    elif composite >= 40:
        risk_label = RiskLabel.MODERATE
    else:
        risk_label = RiskLabel.HIGH

    if not risk_factors:
        risk_factors.append("No significant risk factors detected.")

    return RiskScoreOutput(
        composite_score=composite,
        component_scores=RiskScoreComponentScores(
            emi_ratio_score=round(emi_score, 1),
            buffer_score=round(buffer_score, 1),
            scenario_survival_score=round(scenario_score, 1),
            tenure_age_score=round(tenure_score, 1),
        ),
        risk_label=risk_label,
        risk_factors=risk_factors,
        score_explanation=score_explanation,
    )
