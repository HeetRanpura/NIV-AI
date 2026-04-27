"""
Risk evaluation engine — translates computed metrics into structured
risk signals with causality mapping and weighted scoring.

Deterministic if/then logic only. No LLMs. Every risk flag is
traceable to exact input values and formulas.

Dimensions and weights:
  emi_comfort       25%  — EMI burden relative to household income
  liquidity         30%  — Emergency runway post-purchase
  stress_resilience 25%  — Ability to survive adverse scenarios
  cost_efficiency   10%  — True cost premium vs equivalent renting
  property_risk     10%  — Structural risks from property type and obligations
"""
from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Risk rules — ordered thresholds per dimension
# For lower-is-better metrics: thresholds are upper-bound limits checked
#   in ascending order; first limit >= metric value wins.
# For higher-is-better metrics: thresholds are lower-bound minimums checked
#   in descending order; first limit <= metric value wins.
# ---------------------------------------------------------------------------

RISK_RULES: list[dict] = [
    {
        "id": "emi_comfort",
        "display_name": "EMI Comfort",
        "description": "Monthly EMI burden relative to household income",
        "metric": "emi_to_income_ratio",
        "weight": 0.25,
        "higher_is_better": False,
        "thresholds": [
            {
                "limit": 0.25,
                "score": 90,
                "label": "Comfortable",
                "state": "green",
                "root_cause": "EMI ≤25% of income — healthy headroom for savings and lifestyle",
            },
            {
                "limit": 0.30,
                "score": 72,
                "label": "Acceptable",
                "state": "green",
                "root_cause": "EMI within 30% safe ceiling per RBI advisory",
            },
            {
                "limit": 0.40,
                "score": 45,
                "label": "Stretched",
                "state": "yellow",
                "root_cause": "EMI exceeds 30% threshold — discretionary spending significantly constrained",
            },
            {
                "limit": 0.50,
                "score": 22,
                "label": "High",
                "state": "orange",
                "root_cause": "EMI >40% of income — minimal buffer for unexpected expenses or income dip",
            },
            {
                "limit": math.inf,
                "score": 5,
                "label": "Critical",
                "state": "red",
                "root_cause": "EMI >50% of income — severe financial stress almost certain",
            },
        ],
        "reversibility": "medium",
    },
    {
        "id": "liquidity",
        "display_name": "Liquidity Buffer",
        "description": "Emergency runway: months of obligations covered by post-purchase savings",
        "metric": "emergency_runway_months",
        "weight": 0.30,
        "higher_is_better": True,
        "thresholds": [
            {
                "limit": 12.0,
                "score": 92,
                "label": "Excellent",
                "state": "green",
                "root_cause": ">12 months runway — resilient to prolonged income disruption",
            },
            {
                "limit": 9.0,
                "score": 76,
                "label": "Good",
                "state": "green",
                "root_cause": "9–12 months runway — adequate buffer for most disruption scenarios",
            },
            {
                "limit": 6.0,
                "score": 55,
                "label": "Adequate",
                "state": "yellow",
                "root_cause": "6–9 months — meets minimum recommendation with little spare margin",
            },
            {
                "limit": 3.0,
                "score": 28,
                "label": "Thin",
                "state": "orange",
                "root_cause": "3–6 months — high vulnerability to any income disruption",
            },
            {
                "limit": 0.0,
                "score": 7,
                "label": "Critical",
                "state": "red",
                "root_cause": "<3 months runway — default risk materialises under any adverse income event",
            },
        ],
        "reversibility": "high",
    },
    {
        "id": "stress_resilience",
        "display_name": "Stress Resilience",
        "description": "Estimated ability to survive adverse financial scenarios",
        "metric": "stress_pass_rate",
        "weight": 0.25,
        "higher_is_better": True,
        "thresholds": [
            {
                "limit": 1.00,
                "score": 90,
                "label": "Resilient",
                "state": "green",
                "root_cause": "Survives all stress scenarios — robust against income and rate shocks",
            },
            {
                "limit": 0.75,
                "score": 68,
                "label": "Mostly Resilient",
                "state": "green",
                "root_cause": "Survives most scenarios — minor vulnerability under extreme conditions",
            },
            {
                "limit": 0.50,
                "score": 42,
                "label": "Moderate",
                "state": "yellow",
                "root_cause": "Survives roughly half scenarios — meaningful tail risk exposure",
            },
            {
                "limit": 0.25,
                "score": 20,
                "label": "Fragile",
                "state": "orange",
                "root_cause": "Fails most stress tests — highly exposed to job loss or rate increases",
            },
            {
                "limit": 0.0,
                "score": 4,
                "label": "Critical",
                "state": "red",
                "root_cause": "Fails all stress scenarios — purchase financially unsurvivable under any shock",
            },
        ],
        "reversibility": "medium",
    },
    {
        "id": "cost_efficiency",
        "display_name": "Cost Efficiency",
        "description": "Premium paid for ownership versus equivalent renting",
        "metric": "rent_vs_buy_premium_pct",
        "weight": 0.10,
        "higher_is_better": False,
        "thresholds": [
            {
                "limit": 10.0,
                "score": 88,
                "label": "Efficient",
                "state": "green",
                "root_cause": "Buying costs <10% more than renting — efficient allocation of capital",
            },
            {
                "limit": 30.0,
                "score": 65,
                "label": "Moderate Premium",
                "state": "yellow",
                "root_cause": "Buying 10–30% more expensive than renting — within accepted range for ownership benefits",
            },
            {
                "limit": 60.0,
                "score": 38,
                "label": "High Premium",
                "state": "orange",
                "root_cause": "Buying 30–60% more expensive than renting — cost of ownership is significantly elevated",
            },
            {
                "limit": math.inf,
                "score": 14,
                "label": "Very High Premium",
                "state": "red",
                "root_cause": "Buying >60% more expensive than renting — severely unfavourable unit economics",
            },
        ],
        "reversibility": "low",
    },
    {
        "id": "property_risk",
        "display_name": "Property Risk",
        "description": "Structural risks from property type, construction stage, and existing obligations",
        "metric": "property_risk_score",
        "weight": 0.10,
        "higher_is_better": False,
        "thresholds": [
            {
                "limit": 15,
                "score": 88,
                "label": "Low Risk",
                "state": "green",
                "root_cause": "Ready-to-move, manageable obligations — minimal structural risk",
            },
            {
                "limit": 35,
                "score": 62,
                "label": "Moderate Risk",
                "state": "yellow",
                "root_cause": "Some risk factors present — standard due diligence applies",
            },
            {
                "limit": 60,
                "score": 35,
                "label": "High Risk",
                "state": "orange",
                "root_cause": "Multiple risk factors — enhanced due diligence required before proceeding",
            },
            {
                "limit": math.inf,
                "score": 10,
                "label": "Critical Risk",
                "state": "red",
                "root_cause": "Under-construction with high obligations or volatile income — extreme structural risk",
            },
        ],
        "reversibility": "low",
    },
]

# Score bands for composite label
_COMPOSITE_BANDS = [
    (80, "Financially Sound"),
    (65, "Acceptable Risk"),
    (50, "Elevated Risk"),
    (35, "High Risk"),
    (0,  "Critical Risk"),
]

# Reversibility map for output
_REVERSIBILITY = {rule["id"]: rule["reversibility"] for rule in RISK_RULES}


def _derive_stress_pass_rate(computed: dict) -> float:
    """
    Derives a proxy stress pass rate from computed_dict metrics.
    Mirrors the four canonical stress tests (job loss, rate hike, expense shock, stagnation).
    """
    runway = computed.get("emergency_runway_months", 0)
    emi_ratio = computed.get("emi_to_income_ratio", 1.0)
    dp_ratio = computed.get("down_payment_to_savings_ratio", 1.0)

    passed = 0
    # Job loss (6 months): survives if runway >= 6
    if runway >= 6:
        passed += 1
    # Rate hike (+2%): proxy — if current EMI ratio < 0.48, a ~10% EMI increase stays under 50%
    if emi_ratio < 0.48:
        passed += 1
    # Expense shock (₹5L): survives if dp_ratio < 0.75 (savings not fully depleted)
    if dp_ratio < 0.75:
        passed += 1
    # Income stagnation: survives if current EMI ratio < 0.45 (3yr real-income decline still < 50%)
    if emi_ratio < 0.45:
        passed += 1

    return passed / 4


def _derive_property_risk_score(computed: dict, raw_input: dict) -> int:
    """
    Computes a 0-100 property risk score from raw_input flags and computed ratios.
    Higher = worse. Components:
      Under-construction: +30
      Existing EMI obligations > 15% income: +15
      Volatile employment (freelance/business): +20
      Dependents > 2: +8
      Savings fully depleted (dp_ratio > 0.85): +15
      Savings thin (dp_ratio 0.60-0.85): +8
    """
    prop = raw_input.get("property", {})
    fin = raw_input.get("financial", {})

    score = 0

    if not prop.get("is_ready_to_move", True):
        score += 30

    monthly_income = (
        float(fin.get("monthly_income") or 0)
        + float(fin.get("spouse_income") or 0)
    )
    existing_emis = float(fin.get("existing_emis") or 0)
    if monthly_income > 0 and (existing_emis / monthly_income) > 0.15:
        score += 15

    employment_type = str(fin.get("employment_type") or "").lower()
    if employment_type in ("freelance", "business"):
        score += 20

    dependents = int(fin.get("dependents") or 0)
    if dependents > 2:
        score += 8

    dp_ratio = computed.get("down_payment_to_savings_ratio", 0.0)
    if dp_ratio > 0.85:
        score += 15
    elif dp_ratio > 0.60:
        score += 8

    return min(score, 100)


def _match_threshold(rule: dict, value: float) -> dict:
    """Finds the matching threshold entry for a metric value."""
    thresholds = rule["thresholds"]
    higher_is_better = rule.get("higher_is_better", False)

    if higher_is_better:
        # Descending order: first limit <= value wins
        for t in thresholds:
            if value >= t["limit"]:
                return t
        return thresholds[-1]
    else:
        # Ascending order: first limit >= value wins
        for t in thresholds:
            if value <= t["limit"]:
                return t
        return thresholds[-1]


def evaluate_risk(computed: dict, raw_input: dict) -> dict:
    """
    Evaluates all risk rules and produces a weighted composite score.

    For each rule, finds matching threshold, records score/label/state/root_cause,
    and applies weight to the composite.

    Args:
        computed: compute_all().to_dict() output
        raw_input: Original user input dict (contains "financial" and "property" sub-dicts)

    Returns:
        Dict with:
          composite_score (0-100): weighted average across all dimensions
          composite_label: human-readable band label
          rule_scores: per-dimension breakdown (score, label, state, root_cause, value, weight)
          worst_dimension: dimension id with lowest raw score
          best_dimension: dimension id with highest raw score
          action_priority: list of dimension ids sorted worst-first
          reversibility: dict mapping dimension id → reversibility level
    """
    # Derive computed values for synthetic metrics
    stress_pass_rate = _derive_stress_pass_rate(computed)
    property_risk_score = _derive_property_risk_score(computed, raw_input)

    synthetic = {
        "stress_pass_rate": stress_pass_rate,
        "property_risk_score": property_risk_score,
    }

    rule_scores: dict = {}
    weighted_total = 0.0

    for rule in RISK_RULES:
        metric = rule["metric"]
        value = synthetic.get(metric, computed.get(metric, 0.0))
        matched = _match_threshold(rule, value)

        rule_scores[rule["id"]] = {
            "score": matched["score"],
            "label": matched["label"],
            "state": matched["state"],
            "root_cause": matched["root_cause"],
            "value": round(value, 4) if isinstance(value, float) else value,
            "weight": rule["weight"],
            "display_name": rule["display_name"],
            "weighted_contribution": round(matched["score"] * rule["weight"], 2),
        }
        weighted_total += matched["score"] * rule["weight"]

    composite_score = round(weighted_total, 1)

    composite_label = "Critical Risk"
    for threshold, label in _COMPOSITE_BANDS:
        if composite_score >= threshold:
            composite_label = label
            break

    # Sort dimensions by score ascending (worst first)
    sorted_dims = sorted(rule_scores.items(), key=lambda kv: kv[1]["score"])
    worst_dimension = sorted_dims[0][0]
    best_dimension = sorted_dims[-1][0]
    action_priority = [dim_id for dim_id, _ in sorted_dims]

    return {
        "composite_score": composite_score,
        "composite_label": composite_label,
        "rule_scores": rule_scores,
        "worst_dimension": worst_dimension,
        "best_dimension": best_dimension,
        "action_priority": action_priority,
        "reversibility": _REVERSIBILITY.copy(),
        "stress_pass_rate": round(stress_pass_rate, 3),
        "property_risk_score": property_risk_score,
    }


# ---------------------------------------------------------------------------
# Action pool — each action has a trigger condition, improvement potential,
# feasibility, and metadata
# ---------------------------------------------------------------------------

_ACTION_POOL: list[dict] = [
    {
        "id": "increase_down_payment",
        "trigger_dims": ["emi_comfort", "liquidity"],
        "trigger_fn": lambda rs, c: (
            rs.get("emi_comfort", {}).get("score", 100) < 55
            or rs.get("liquidity", {}).get("score", 100) < 55
        ),
        "action": "Increase down payment before purchasing",
        "impact": "Directly lowers EMI and improves post-purchase liquidity ratio",
        "effort": "High — requires additional saving over 6–18 months",
        "timeframe": "6–18 months",
        "reversibility": "Irreversible",
        "improvement_potential": 28,
        "feasibility_score": 0.70,
    },
    {
        "id": "extend_loan_tenure",
        "trigger_dims": ["emi_comfort"],
        "trigger_fn": lambda rs, c: rs.get("emi_comfort", {}).get("score", 100) < 50,
        "action": "Extend loan tenure to 25–30 years",
        "impact": "Reduces monthly EMI by 10–20%, immediately improving income buffer",
        "effort": "Low — request longer tenure at application",
        "timeframe": "Immediate (at loan application)",
        "reversibility": "Reversible via prepayment",
        "improvement_potential": 18,
        "feasibility_score": 0.90,
    },
    {
        "id": "build_emergency_fund",
        "trigger_dims": ["liquidity", "stress_resilience"],
        "trigger_fn": lambda rs, c: (
            rs.get("liquidity", {}).get("score", 100) < 60
            or rs.get("stress_resilience", {}).get("score", 100) < 50
        ),
        "action": "Build 6-month emergency fund before purchase",
        "impact": "Raises emergency runway above minimum safe threshold; improves stress resilience",
        "effort": "Medium — systematic monthly savings before closing",
        "timeframe": "3–12 months depending on gap",
        "reversibility": "Fully reversible",
        "improvement_potential": 25,
        "feasibility_score": 0.75,
    },
    {
        "id": "reduce_existing_emis",
        "trigger_dims": ["emi_comfort", "property_risk"],
        "trigger_fn": lambda rs, c: (
            c.get("emi_to_income_ratio", 0) > 0.35
            and rs.get("property_risk", {}).get("value", 0) > 15
        ),
        "action": "Clear or reduce existing loan obligations before applying",
        "impact": "Lowers total debt-to-income ratio and improves bank eligibility",
        "effort": "High — requires prepaying or closing existing loans",
        "timeframe": "3–12 months",
        "reversibility": "Irreversible (prepayment)",
        "improvement_potential": 20,
        "feasibility_score": 0.55,
    },
    {
        "id": "choose_ready_to_move",
        "trigger_dims": ["property_risk"],
        "trigger_fn": lambda rs, c: rs.get("property_risk", {}).get("score", 100) < 60,
        "action": "Prefer ready-to-move property over under-construction",
        "impact": "Eliminates delivery risk, pre-EMI interest, and RERA delay exposure",
        "effort": "Medium — may require budget adjustment or location flexibility",
        "timeframe": "Immediate (at property selection)",
        "reversibility": "Fully reversible",
        "improvement_potential": 22,
        "feasibility_score": 0.60,
    },
    {
        "id": "negotiate_property_price",
        "trigger_dims": ["emi_comfort", "cost_efficiency"],
        "trigger_fn": lambda rs, c: (
            rs.get("cost_efficiency", {}).get("score", 100) < 55
            or rs.get("emi_comfort", {}).get("score", 100) < 45
        ),
        "action": "Negotiate a lower property price or switch to a smaller unit",
        "impact": "Reduces loan principal, EMI, and total interest outgo simultaneously",
        "effort": "Medium — market-dependent negotiation",
        "timeframe": "Immediate (at purchase negotiation)",
        "reversibility": "N/A",
        "improvement_potential": 24,
        "feasibility_score": 0.50,
    },
    {
        "id": "maintain_financial_discipline",
        "trigger_dims": [],
        "trigger_fn": lambda rs, c: True,  # always available as fallback
        "action": "Maintain strict spending discipline after purchase",
        "impact": "Prevents savings erosion and keeps emergency fund intact",
        "effort": "Low — behavioural commitment",
        "timeframe": "Ongoing",
        "reversibility": "Fully reversible",
        "improvement_potential": 10,
        "feasibility_score": 0.85,
    },
]


def get_action_plan(risk_evaluation: dict, computed: dict) -> list[dict]:
    """
    Generates 3–5 prioritised actions from risk evaluation.

    Ranks by (improvement_potential * feasibility_score).
    Each action includes: action, impact, effort, timeframe, reversibility.

    Args:
        risk_evaluation: Output from evaluate_risk()
        computed: compute_all().to_dict()

    Returns:
        List of action dicts, highest impact first (3–5 items).
    """
    rule_scores = risk_evaluation.get("rule_scores", {})
    eligible: list[dict] = []

    for template in _ACTION_POOL:
        try:
            triggered = template["trigger_fn"](rule_scores, computed)
        except Exception:
            triggered = False

        if not triggered:
            continue

        rank_score = template["improvement_potential"] * template["feasibility_score"]
        eligible.append({
            "action": template["action"],
            "impact": template["impact"],
            "effort": template["effort"],
            "timeframe": template["timeframe"],
            "reversibility": template["reversibility"],
            "_rank": rank_score,
        })

    # Sort descending by rank
    eligible.sort(key=lambda a: a["_rank"], reverse=True)

    # Return 3–5 actions, strip internal rank key
    result = []
    for action in eligible[:5]:
        result.append({k: v for k, v in action.items() if k != "_rank"})

    # Ensure at least 3 items — pad with the maintenance action if needed
    if len(result) < 3:
        fallback = next(
            (a for a in _ACTION_POOL if a["id"] == "maintain_financial_discipline"), None
        )
        if fallback and not any(r["action"] == fallback["action"] for r in result):
            result.append({
                "action": fallback["action"],
                "impact": fallback["impact"],
                "effort": fallback["effort"],
                "timeframe": fallback["timeframe"],
                "reversibility": fallback["reversibility"],
            })

    return result
