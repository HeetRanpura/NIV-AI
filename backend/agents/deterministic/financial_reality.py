"""
Financial Reality Agent — Pure math, no AI.
Standard amortization formula. Deterministic output for the same inputs every time.
No imports from Dev 2's files.

Feature additions:
  Feature 3: Bank FOIR (Eligibility) Underwriting Check
    - Computes total FOIR = (new EMI + existing EMIs) / monthly income
    - Flags breach if FOIR > 50% (RBI benchmark)

  Feature 5: Property Age & Structural Depreciation Factor
    - RCC building expected lifespan: 60 years
    - Banks typically reduce LTV below standard 80% for buildings >20 yrs old
    - Buildings >40 yrs: max LTV 50–60%; structurally risky
"""
from datetime import date
from typing import Optional, Tuple
from schemas.schemas import (
    UserInput, FinancialRealityOutput, AffordabilityStatus, IndiaCostBreakdown
)
from engines.india_defaults import calculate_true_total_cost


# ---------------------------------------------------------------------------
# EMI helpers
# ---------------------------------------------------------------------------

def _calculate_emi(principal: float, annual_rate: float, tenure_years: int) -> float:
    """Standard EMI amortization formula: EMI = P * r * (1+r)^n / ((1+r)^n - 1)"""
    if principal <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (tenure_years * 12)

    r = annual_rate / 12.0
    n = tenure_years * 12
    power = (1 + r) ** n
    emi = principal * r * power / (power - 1)
    return emi


def _reverse_loan_from_emi(target_emi: float, annual_rate: float, tenure_years: int) -> float:
    """Given a target EMI, back-calculate the maximum loan principal."""
    if target_emi <= 0:
        return 0.0
    if annual_rate <= 0:
        return target_emi * tenure_years * 12

    r = annual_rate / 12.0
    n = tenure_years * 12
    power = (1 + r) ** n
    principal = target_emi * (power - 1) / (r * power)
    return principal


# ---------------------------------------------------------------------------
# Feature 3: FOIR Underwriting Check
# ---------------------------------------------------------------------------

FOIR_LIMIT = 0.50   # RBI benchmark; some banks use 0.55 for HNI

def _compute_foir(
    emi: float,
    existing_obligations: float,
    monthly_income: float,
) -> Tuple[float, bool, Optional[str]]:
    """
    Returns (foir_ratio, foir_breach, warning_message).

    foir_ratio = (new_EMI + all_existing_EMIs) / monthly_income
    """
    if monthly_income <= 0:
        return 1.0, True, "Income not provided — FOIR cannot be calculated."

    total_obligations = emi + existing_obligations
    foir = total_obligations / monthly_income

    if foir > FOIR_LIMIT:
        warning = (
            f"FOIR is {foir*100:.1f}% — exceeds the RBI 50% underwriting limit. "
            f"Total monthly debt (₹{total_obligations:,.0f}) on income of "
            f"₹{monthly_income:,.0f} will likely trigger a bank rejection. "
            f"Consider reducing loan amount or increasing income documentation."
        )
        return round(foir, 4), True, warning

    return round(foir, 4), False, None


# ---------------------------------------------------------------------------
# Feature 5: Property Age & Structural Depreciation
# ---------------------------------------------------------------------------

RCC_LIFESPAN_YEARS = 60       # Standard RCC building life expectancy
LTV_STANDARD        = 0.80    # Bank standard LTV for properties < 20 yrs
LTV_MODERATE        = 0.70    # 20–30 yrs old
LTV_AGED            = 0.60    # 30–40 yrs old
LTV_OLD             = 0.50    # > 40 yrs old


def _compute_depreciation(
    construction_year: Optional[int],
) -> Tuple[Optional[int], Optional[float], bool, Optional[str]]:
    """
    Returns (structural_life_remaining, ltv_recommended_pct, ltv_age_risk, warning).
    """
    if construction_year is None:
        return None, None, False, None

    current_year  = date.today().year
    building_age  = current_year - construction_year
    life_remaining = max(0, RCC_LIFESPAN_YEARS - building_age)

    if building_age < 20:
        ltv_pct = LTV_STANDARD
        risk    = False
        warning = None
    elif building_age < 30:
        ltv_pct = LTV_MODERATE
        risk    = True
        warning = (
            f"Building is {building_age} years old. Banks may restrict LTV to 70% "
            f"(vs. standard 80%), increasing the required down payment significantly."
        )
    elif building_age < 40:
        ltv_pct = LTV_AGED
        risk    = True
        warning = (
            f"Building is {building_age} years old — entering the aging bracket. "
            f"Expect bank LTV of ~60%. Structural survey strongly recommended before purchase."
        )
    else:
        ltv_pct = LTV_OLD
        risk    = True
        warning = (
            f"CRITICAL: Building is {building_age} years old with only "
            f"~{life_remaining} years of structural life remaining. "
            f"Banks typically offer max LTV of 50%. High risk of future maintenance "
            f"levy, redevelopment disputes, and difficulty reselling."
        )

    return life_remaining, ltv_pct, risk, warning


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------

def calculate_affordability(user_input: UserInput) -> FinancialRealityOutput:
    """
    Calculates the complete financial reality of a home purchase.
    Pure math. Zero LLM involvement. Deterministic.
    """
    # --- India cost breakdown (now with GST slab, district stamp duty, hidden fees) ---
    loan_amount = user_input.property_price - user_input.down_payment
    if loan_amount < 0:
        loan_amount = 0.0

    india_cost_breakdown = calculate_true_total_cost(
        base_price=user_input.property_price,
        state=user_input.state,
        property_type=user_input.property_type.value,
        loan_amount=loan_amount,
        area_sqft=user_input.area_sqft if user_input.area_sqft else 1000,
        area_sqm=user_input.area_sqm,
        district=user_input.district,
        is_female_buyer=user_input.is_female_buyer,
    )

    # --- EMI calculation ---
    emi = _calculate_emi(loan_amount, user_input.annual_interest_rate, user_input.tenure_years)

    # --- Total interest payable ---
    tenure_months = user_input.tenure_years * 12
    if loan_amount > 0:
        total_interest_payable = (emi * tenure_months) - loan_amount
    else:
        total_interest_payable = 0.0

    # --- Financial health metrics ---
    emi_to_income_ratio = emi / user_input.monthly_income if user_input.monthly_income > 0 else float("inf")
    monthly_surplus_after_emi = user_input.monthly_income - user_input.monthly_expenses - emi

    # --- 12-month cash flow projection ---
    cash_flow_12_months = []
    running_savings = user_input.total_savings - user_input.down_payment
    savings_depletion_month = None

    for month in range(1, 13):
        running_savings += monthly_surplus_after_emi
        cash_flow_12_months.append(round(running_savings, 2))
        if running_savings <= 0 and savings_depletion_month is None:
            savings_depletion_month = month

    # --- Safe and maximum property prices ---
    target_emi_safe = user_input.monthly_income * 0.35
    safe_loan = _reverse_loan_from_emi(target_emi_safe, user_input.annual_interest_rate, user_input.tenure_years)
    safe_property_price = safe_loan + user_input.down_payment

    target_emi_max = user_input.monthly_income * 0.50
    max_loan = _reverse_loan_from_emi(target_emi_max, user_input.annual_interest_rate, user_input.tenure_years)
    maximum_property_price = max_loan + user_input.down_payment

    # --- Affordability status ---
    if emi_to_income_ratio <= 0.35:
        affordability_status = AffordabilityStatus.COMFORTABLE
    elif emi_to_income_ratio <= 0.50:
        affordability_status = AffordabilityStatus.STRETCHED
    else:
        affordability_status = AffordabilityStatus.OVEREXTENDED

    # --- Feature 3: FOIR Underwriting Check ---
    foir_ratio, foir_breach, foir_warning = _compute_foir(
        emi=emi,
        existing_obligations=user_input.existing_emi_obligations,
        monthly_income=user_input.monthly_income,
    )

    # --- Feature 5: Property Age & Structural Depreciation ---
    structural_life_remaining, ltv_recommended_pct, ltv_age_risk, age_depreciation_warning = (
        _compute_depreciation(user_input.construction_year)
    )

    return FinancialRealityOutput(
        emi=round(emi, 2),
        emi_to_income_ratio=round(emi_to_income_ratio, 4),
        monthly_surplus_after_emi=round(monthly_surplus_after_emi, 2),
        cash_flow_12_months=cash_flow_12_months,
        savings_depletion_month=savings_depletion_month,
        safe_property_price=round(safe_property_price, 2),
        maximum_property_price=round(maximum_property_price, 2),
        affordability_status=affordability_status,
        india_cost_breakdown=india_cost_breakdown,
        loan_amount=round(loan_amount, 2),
        total_interest_payable=round(total_interest_payable, 2),
        # Feature 3: FOIR
        foir_ratio=foir_ratio,
        foir_limit=FOIR_LIMIT,
        foir_breach=foir_breach,
        foir_warning=foir_warning,
        # Feature 5: Depreciation
        structural_life_remaining=structural_life_remaining,
        ltv_recommended_pct=ltv_recommended_pct,
        ltv_age_risk=ltv_age_risk,
        age_depreciation_warning=age_depreciation_warning,
    )
