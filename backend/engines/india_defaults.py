"""
India real estate hidden cost calculations.

Feature upgrades (Institutional-Grade Financial Math):
  1. Dynamic GST Slab Auto-Classifier
     - 0% for ready-to-move
     - 1% for affordable housing (≤₹45L AND ≤90 sqm carpet area)
     - 5% for all other under-construction properties

  2. Exact District-Level Stamp Duty Engine
     - District-level overrides for MH, DL, KA, TN, GJ, HR
     - 1% female buyer concession where applicable

  3. Bank FOIR (Eligibility) Underwriting Check  [computed in financial_reality.py]

  4. The "Hidden Fee" Aggregator
     - Bank processing fee (SBI 0.35% benchmark)
     - Legal / technical verification fee
     - Annual BMC / municipal property tax estimate

  5. Property Age & Structural Depreciation Factor  [computed in financial_reality.py]

No AI. Pure data and math.
"""
import math
from datetime import date
from typing import Optional, Dict, Tuple, Set
from schemas.schemas import IndiaCostBreakdown



# ---------------------------------------------------------------------------
# Feature 1: GST Slab Classification
# ---------------------------------------------------------------------------

AFFORDABLE_HOUSING_PRICE_LIMIT = 4_500_000   # ₹45 lakh
AFFORDABLE_HOUSING_SQM_LIMIT   = 90          # 90 sq metres carpet area

GST_SLAB_EXEMPT        = "exempt"
GST_SLAB_AFFORDABLE    = "affordable_1pct"
GST_SLAB_STANDARD      = "standard_5pct"


def _classify_gst_slab(
    property_type: str,
    base_price: float,
    area_sqm: Optional[float],
) -> Tuple[str, float, float]:
    """
    Determines the correct GST slab.

    Returns:
        (slab_code, gst_rate, gst_amount)
    """
    if property_type != "under_construction":
        return GST_SLAB_EXEMPT, 0.0, 0.0

    # Affordable housing: price ≤ ₹45L AND carpet area ≤ 90 sqm
    if (
        base_price <= AFFORDABLE_HOUSING_PRICE_LIMIT
        and area_sqm is not None
        and area_sqm <= AFFORDABLE_HOUSING_SQM_LIMIT
    ):
        return GST_SLAB_AFFORDABLE, 0.01, base_price * 0.01

    return GST_SLAB_STANDARD, 0.05, base_price * 0.05


# ---------------------------------------------------------------------------
# Feature 2: District-Level Stamp Duty Engine
# ---------------------------------------------------------------------------

# State-level base rates (2024-25)
STATE_STAMP_DUTY_RATES: Dict[str, float] = {
    "maharashtra":      0.05,
    "karnataka":        0.056,
    "delhi":            0.06,
    "tamil_nadu":       0.07,
    "gujarat":          0.045,
    "rajasthan":        0.06,
    "west_bengal":      0.06,
    "telangana":        0.05,
    "andhra_pradesh":   0.05,
    "punjab":           0.07,
    "haryana":          0.07,
    "uttar_pradesh":    0.07,
    "madhya_pradesh":   0.075,
    "kerala":           0.08,
    "goa":              0.035,
}

# District-level overrides (state → district → rate)
DISTRICT_STAMP_DUTY_OVERRIDES: dict[str, Dict[str, float]] = {
    "maharashtra": {
        "mumbai_city":    0.05,    # flat 5% (registration capped ₹30k)
        "mumbai_suburban":0.05,
        "pune":           0.07,    # Pune adds 1% metro cess + LBT
        "thane":          0.07,
        "nagpur":         0.06,
        "nashik":         0.06,
        "aurangabad":     0.06,
    },
    "delhi": {
        "new_delhi":      0.06,    # male buyer
        "south_delhi":    0.06,
        "north_delhi":    0.06,
        "east_delhi":     0.06,
        "west_delhi":     0.06,
        "central_delhi":  0.06,
    },
    "karnataka": {
        "bengaluru_urban":0.056,
        "mysuru":         0.056,
        "mangaluru":      0.056,
        "hubballi":       0.056,
    },
    "tamil_nadu": {
        "chennai":        0.07,
        "coimbatore":     0.07,
        "madurai":        0.07,
        "tiruchirappalli":0.07,
    },
    "haryana": {
        "gurugram":       0.07,
        "faridabad":      0.07,
        "sonipat":        0.07,
        "panipat":        0.07,
    },
    "gujarat": {
        "ahmedabad":      0.045,
        "surat":          0.045,
        "vadodara":       0.045,
        "rajkot":         0.045,
    },
}

# States that offer female buyer concession (1% off stamp duty)
FEMALE_CONCESSION_STATES: Set[str] = {
    "maharashtra", "delhi", "haryana", "uttar_pradesh",
    "rajasthan", "punjab", "himachal_pradesh",
}

DEFAULT_STAMP_DUTY_RATE = 0.06


def _calculate_stamp_duty(
    base_price: float,
    state: str,
    district: Optional[str],
    is_female_buyer: bool,
) -> tuple[float, float, bool]:
    """
    Returns (stamp_duty_amount, effective_rate, concession_applied).
    """
    # Look up district first, fall back to state, then global default
    state_districts = DISTRICT_STAMP_DUTY_OVERRIDES.get(state, {})
    if district and district in state_districts:
        base_rate = state_districts[district]
    else:
        base_rate = STATE_STAMP_DUTY_RATES.get(state, DEFAULT_STAMP_DUTY_RATE)

    # Apply female buyer concession
    concession_applied = False
    if is_female_buyer and state in FEMALE_CONCESSION_STATES:
        effective_rate = max(0.0, base_rate - 0.01)
        concession_applied = True
    else:
        effective_rate = base_rate

    stamp_duty = base_price * effective_rate
    return stamp_duty, effective_rate, concession_applied


# ---------------------------------------------------------------------------
# Feature 4: Hidden Fee Aggregator
# ---------------------------------------------------------------------------

# Bank processing fee (SBI benchmark: 0.35%, min ₹2k max ₹10k)
BANK_PROCESSING_FEE_RATE = 0.0035
BANK_PROCESSING_FEE_MIN  = 2_000
BANK_PROCESSING_FEE_MAX  = 10_000

# Legal / technical verification fee charged by bank (approximate)
LEGAL_VERIFICATION_FEE = 8_500.0

# Annual municipal property tax: approximately 0.1% of property value
# (BMC in Mumbai charges ₹1–3/sqft/year; 0.1% is a conservative city estimate)
ANNUAL_PROPERTY_TAX_RATE = 0.001


def _compute_hidden_fees(
    loan_amount: float,
    base_price: float,
) -> Tuple[float, float, float]:
    """
    Returns (bank_processing_fee, legal_verification_fee, annual_property_tax).
    """
    bank_fee = loan_amount * BANK_PROCESSING_FEE_RATE
    bank_fee = max(BANK_PROCESSING_FEE_MIN, min(BANK_PROCESSING_FEE_MAX, bank_fee))
    annual_tax = base_price * ANNUAL_PROPERTY_TAX_RATE
    return round(bank_fee, 2), round(LEGAL_VERIFICATION_FEE, 2), round(annual_tax, 2)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def calculate_true_total_cost(
    base_price: float,
    state: str,
    property_type: str,
    loan_amount: float,
    area_sqft: float = 1000,
    maintenance_per_sqft: float = 3.0,
    # Feature 1
    area_sqm: Optional[float] = None,
    # Feature 2
    district: Optional[str] = None,
    is_female_buyer: bool = False,
) -> IndiaCostBreakdown:
    """
    Calculates the true total cost of acquiring an Indian property,
    including all hidden fees that buyers typically don't account for.

    Feature upgrades included:
      - GST auto-classification (0% / 1% affordable / 5% standard)
      - District-level stamp duty with female buyer concession
      - Itemised bank processing fee, legal verification fee, annual property tax
    """
    normalized_state    = state.lower().strip().replace(" ", "_")
    normalized_district = district.lower().strip().replace(" ", "_") if district else None

    # --- Feature 2: Stamp duty (district-aware, female concession) ---
    stamp_duty, stamp_duty_rate, female_concession = _calculate_stamp_duty(
        base_price=base_price,
        state=normalized_state,
        district=normalized_district,
        is_female_buyer=is_female_buyer,
    )

    # --- Registration fee ---
    # Generally 1% across India
    registration_fee = base_price * 0.01
    # Maharashtra specific cap: max ₹30,000
    if normalized_state == "maharashtra" and registration_fee > 30_000:
        registration_fee = 30_000.0

    # --- Feature 1: GST Auto-Classifier ---
    gst_slab, _gst_rate, gst = _classify_gst_slab(property_type, base_price, area_sqm)
    gst_applicable = gst_slab != GST_SLAB_EXEMPT

    # --- Maintenance deposit ---
    # Typically 24 months of maintenance upfront
    maintenance_deposit = maintenance_per_sqft * area_sqft * 24.0

    # --- Loan processing fee (legacy, kept for backward compat) ---
    # Now superseded by itemised bank_processing_fee below
    loan_processing_fee = loan_amount * 0.0075

    # --- Feature 4: Hidden fee aggregator ---
    bank_processing_fee, legal_verification_fee, annual_property_tax = _compute_hidden_fees(
        loan_amount=loan_amount,
        base_price=base_price,
    )

    # --- Legacy legal charges (solicitor / title search) ---
    legal_charges = 15_000.0

    # --- True total cost ---
    true_total_cost = (
        base_price
        + stamp_duty
        + registration_fee
        + gst
        + maintenance_deposit
        + bank_processing_fee      # replaces old loan_processing_fee in true cost
        + legal_verification_fee
        + legal_charges
        # annual_property_tax is recurring so NOT added to one-time true_total_cost
        # but surfaced separately in the breakdown for transparency
    )

    # --- Tax benefits ---
    tax_benefit_80c = 150_000.0   # Section 80C: max ₹1.5L/yr on principal
    tax_benefit_24b = 200_000.0   # Section 24B: max ₹2L/yr on interest

    return IndiaCostBreakdown(
        base_price=base_price,
        stamp_duty=round(stamp_duty, 2),
        stamp_duty_rate=round(stamp_duty_rate, 4),
        female_buyer_concession_applied=female_concession,
        registration_fee=round(registration_fee, 2),
        gst=round(gst, 2),
        gst_applicable=gst_applicable,
        gst_slab=gst_slab,
        maintenance_deposit=round(maintenance_deposit, 2),
        loan_processing_fee=round(loan_processing_fee, 2),
        bank_processing_fee=bank_processing_fee,
        legal_verification_fee=legal_verification_fee,
        annual_property_tax=annual_property_tax,
        legal_charges=round(legal_charges, 2),
        true_total_cost=round(true_total_cost, 2),
        tax_benefit_80c=tax_benefit_80c,
        tax_benefit_24b=tax_benefit_24b,
    )
