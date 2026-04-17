"""
India real estate hidden cost calculations.
All stamp duty rates, registration fees, GST, maintenance deposit,
loan processing, legal charges, and Section 80C/24B tax benefits.
No AI. Pure data and math.
"""
from typing import Optional, Tuple

from schemas.schemas import IndiaCostBreakdown


# State-specific stamp duty rates
STAMP_DUTY_RATES = {
    "maharashtra": 0.05,
    "karnataka": 0.056,
    "delhi": 0.06,
    "tamil_nadu": 0.07,
    "gujarat": 0.045,
    "rajasthan": 0.06,
    "west_bengal": 0.06,
    "telangana": 0.05,
    "andhra_pradesh": 0.05,
    "punjab": 0.07,
    "haryana": 0.07,
    "uttar_pradesh": 0.07,
    "madhya_pradesh": 0.075,
    "kerala": 0.08,
    "goa": 0.035,
}

# Default stamp duty rate if state is not in the lookup
DEFAULT_STAMP_DUTY_RATE = 0.06
CURRENT_REPO_RATE = 0.085
GST_UNDER_CONSTRUCTION = 0.05
GST_READY_TO_MOVE = 0.0
INDIA_DEFAULTS_LAST_UPDATED = "2026-04"

PMAY_BRACKETS = (
    {"max_income": 600000.0, "subsidy_rate": 0.065, "loan_cap": 600000.0, "label": "EWS/LIG"},
    {"max_income": 1200000.0, "subsidy_rate": 0.04, "loan_cap": 900000.0, "label": "MIG-I"},
    {"max_income": 1800000.0, "subsidy_rate": 0.03, "loan_cap": 1200000.0, "label": "MIG-II"},
)
PMAY_DISCOUNT_RATE = 0.09
PMAY_MAX_TENURE_YEARS = 20


def _calculate_emi(principal: float, annual_rate: float, tenure_years: int) -> float:
    if principal <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (tenure_years * 12)

    monthly_rate = annual_rate / 12.0
    months = tenure_years * 12
    growth = (1 + monthly_rate) ** months
    return principal * monthly_rate * growth / (growth - 1)


def calculate_pmay_subsidy(
    annual_income: Optional[float],
    loan_amount: float,
    tenure_years: int,
) -> Tuple[float, bool]:
    """
    Approximate PMAY-CLSS benefit as the discounted present value of EMI savings
    on the scheme-eligible loan tranche. Returns (subsidy_npv, eligible).
    """
    if annual_income is None or annual_income <= 0 or loan_amount <= 0:
        return 0.0, False

    bracket = next(
        (item for item in PMAY_BRACKETS if annual_income <= item["max_income"]),
        None,
    )
    if not bracket:
        return 0.0, False

    eligible_principal = min(loan_amount, bracket["loan_cap"])
    if eligible_principal <= 0:
        return 0.0, False

    effective_tenure_years = max(1, min(tenure_years, PMAY_MAX_TENURE_YEARS))
    base_emi = _calculate_emi(eligible_principal, PMAY_DISCOUNT_RATE, effective_tenure_years)
    subsidized_rate = max(0.0, PMAY_DISCOUNT_RATE - bracket["subsidy_rate"])
    subsidized_emi = _calculate_emi(eligible_principal, subsidized_rate, effective_tenure_years)
    monthly_savings = max(0.0, base_emi - subsidized_emi)

    discount_monthly = PMAY_DISCOUNT_RATE / 12.0
    pv = 0.0
    for month in range(1, effective_tenure_years * 12 + 1):
        pv += monthly_savings / ((1 + discount_monthly) ** month)

    return round(pv, 2), True


def calculate_true_total_cost(
    base_price: float,
    state: str,
    property_type: str,
    loan_amount: float,
    area_sqft: float = 1000,
    maintenance_per_sqft: float = 3.0,
    annual_income: Optional[float] = None,
    tenure_years: int = 20,
) -> IndiaCostBreakdown:
    """
    Calculates the true total cost of acquiring an Indian property,
    including all hidden fees that buyers typically don't account for.

    Args:
        base_price: Listed property price in rupees.
        state: Indian state name (used for stamp duty lookup).
        property_type: "under_construction" or "ready_to_move".
        loan_amount: Principal loan amount in rupees.
        area_sqft: Property area in sq ft for maintenance calculation.
        maintenance_per_sqft: Monthly maintenance rate per sq ft.

    Returns:
        IndiaCostBreakdown with every cost component and the true total.
    """
    normalized_state = state.lower().strip().replace(" ", "_")

    # --- Stamp duty ---
    stamp_duty_rate = STAMP_DUTY_RATES.get(normalized_state, DEFAULT_STAMP_DUTY_RATE)
    stamp_duty = base_price * stamp_duty_rate

    # --- Registration fee ---
    # Generally 1% across India
    registration_fee = base_price * 0.01
    # Maharashtra specific cap: max ₹30,000
    if normalized_state == "maharashtra" and registration_fee > 30000:
        registration_fee = 30000.0

    # --- GST ---
    # 5% on under-construction properties, 0% on ready-to-move
    gst_applicable = property_type == "under_construction"
    if gst_applicable:
        gst = base_price * GST_UNDER_CONSTRUCTION
    else:
        gst = GST_READY_TO_MOVE

    # --- Maintenance deposit ---
    # Typically 24 months of maintenance upfront
    maintenance_deposit = maintenance_per_sqft * area_sqft * 24.0

    # --- Loan processing fee ---
    # 0.75% of loan amount
    loan_processing_fee = loan_amount * 0.0075

    # --- Legal charges ---
    legal_charges = 15000.0

    # --- True total cost ---
    true_total_cost = (
        base_price
        + stamp_duty
        + registration_fee
        + gst
        + maintenance_deposit
        + loan_processing_fee
        + legal_charges
    )

    pmay_subsidy_npv, pmay_eligible = calculate_pmay_subsidy(
        annual_income=annual_income,
        loan_amount=loan_amount,
        tenure_years=tenure_years,
    )
    effective_total_cost = max(0.0, true_total_cost - pmay_subsidy_npv)

    # --- Tax benefits ---
    # Section 80C: deduction on principal repayment, max ₹1,50,000/year
    tax_benefit_80c = 150000.0
    # Section 24B: deduction on interest payment, max ₹2,00,000/year
    tax_benefit_24b = 200000.0

    return IndiaCostBreakdown(
        base_price=base_price,
        stamp_duty=stamp_duty,
        stamp_duty_rate=stamp_duty_rate,
        registration_fee=registration_fee,
        gst=gst,
        gst_applicable=gst_applicable,
        maintenance_deposit=maintenance_deposit,
        loan_processing_fee=loan_processing_fee,
        legal_charges=legal_charges,
        true_total_cost=true_total_cost,
        effective_total_cost=effective_total_cost,
        tax_benefit_80c=tax_benefit_80c,
        tax_benefit_24b=tax_benefit_24b,
        pmay_subsidy_npv=pmay_subsidy_npv,
        pmay_eligible=pmay_eligible,
    )
