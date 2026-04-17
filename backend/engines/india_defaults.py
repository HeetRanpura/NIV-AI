"""
India real estate hidden cost calculations.
All stamp duty rates, registration fees, GST, maintenance deposit,
loan processing, legal charges, and Section 80C/24B tax benefits.
No AI. Pure data and math.
"""
from schemas.schemas import IndiaCostBreakdown


# State-specific stamp duty rates (as of 2024-2025)
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


def calculate_true_total_cost(
    base_price: float,
    state: str,
    property_type: str,
    loan_amount: float,
    area_sqft: float = 1000,
    maintenance_per_sqft: float = 3.0,
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
        gst = base_price * 0.05
    else:
        gst = 0.0

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
        tax_benefit_80c=tax_benefit_80c,
        tax_benefit_24b=tax_benefit_24b,
    )
