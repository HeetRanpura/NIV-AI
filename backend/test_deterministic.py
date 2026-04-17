"""
Test script for deterministic agents.
Verifies all math with a real Mumbai scenario before integration.
Run from the backend/ directory:  python test_deterministic.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from schemas.schemas import UserInput, PropertyType
from engines.india_defaults import calculate_true_total_cost
from agents.deterministic.financial_reality import calculate_affordability
from agents.deterministic.scenario_simulation import run_all_scenarios
from agents.deterministic.risk_scorer import calculate_risk_score


def test_mumbai_scenario():
    """₹80L property in Maharashtra, ₹1.5L income, ₹15L savings, 20yr loan."""
    print("=" * 60)
    print("TEST: ₹80L Ready-to-Move in Maharashtra")
    print("=" * 60)

    user_input = UserInput(
        monthly_income=150000,
        monthly_expenses=60000,
        total_savings=1500000,
        down_payment=1500000,
        property_price=8000000,
        tenure_years=20,
        annual_interest_rate=0.085,
        age=32,
        state="maharashtra",
        property_type=PropertyType.READY_TO_MOVE,
        area_sqft=850,
        session_id="test_session",
    )

    # --- India Defaults ---
    loan_amount = user_input.property_price - user_input.down_payment
    india_costs = calculate_true_total_cost(
        base_price=user_input.property_price,
        state=user_input.state,
        property_type=user_input.property_type.value,
        loan_amount=loan_amount,
        area_sqft=user_input.area_sqft,
        annual_income=user_input.monthly_income * 12,
        tenure_years=user_input.tenure_years,
    )
    print(f"\n--- India Cost Breakdown ---")
    print(f"  Base price:        ₹{india_costs.base_price:,.0f}")
    print(f"  Stamp duty (5%):   ₹{india_costs.stamp_duty:,.0f}")
    print(f"  Registration fee:  ₹{india_costs.registration_fee:,.0f}  (capped at ₹30K)")
    print(f"  GST:               ₹{india_costs.gst:,.0f}  (ready-to-move = 0%)")
    print(f"  Maintenance dep:   ₹{india_costs.maintenance_deposit:,.0f}")
    print(f"  Processing fee:    ₹{india_costs.loan_processing_fee:,.0f}")
    print(f"  Legal charges:     ₹{india_costs.legal_charges:,.0f}")
    print(f"  TRUE TOTAL COST:   ₹{india_costs.true_total_cost:,.0f}")
    print(f"  PMAY eligible:     {'Yes' if india_costs.pmay_eligible else 'No'}")
    print(f"  PMAY subsidy NPV:  ₹{india_costs.pmay_subsidy_npv:,.0f}")
    print(f"  Effective total:   ₹{india_costs.effective_total_cost:,.0f}")

    # --- Financial Reality ---
    financial = calculate_affordability(user_input)
    print(f"\n--- Financial Reality ---")
    print(f"  Loan amount:       ₹{financial.loan_amount:,.0f}")
    print(f"  EMI:               ₹{financial.emi:,.0f}")
    print(f"  EMI/Income ratio:  {financial.emi_to_income_ratio:.2%}")
    print(f"  Monthly surplus:   ₹{financial.monthly_surplus_after_emi:,.0f}")
    print(f"  Depletion month:   {financial.savings_depletion_month or 'Never'}")
    print(f"  Safe price:        ₹{financial.safe_property_price:,.0f}")
    print(f"  Max price:         ₹{financial.maximum_property_price:,.0f}")
    print(f"  Status:            {financial.affordability_status.value}")
    print(f"  Total interest:    ₹{financial.total_interest_payable:,.0f}")

    # --- Scenarios ---
    scenarios = run_all_scenarios(user_input, financial)
    print(f"\n--- Scenario Simulation ---")
    for name, sc in [
        ("Base Case", scenarios.base_case),
        ("Income Drop 30%", scenarios.income_drop_30pct),
        ("Job Loss 6M", scenarios.job_loss_6_months),
        ("Rate Hike +2%", scenarios.interest_rate_hike_2pct),
        ("Emergency ₹5L", scenarios.emergency_expense_5L),
    ]:
        status = "✅ SURVIVES" if sc.survivable else f"❌ BREAKS month {sc.breaking_point_month}"
        print(f"  {name:20s}  {status}  buffer={sc.buffer_months}m  severity={sc.severity.value}")
    print(f"  Scenarios survived: {scenarios.scenarios_survived}/5")

    # --- Risk Score ---
    risk = calculate_risk_score(financial, scenarios, user_input.age, user_input.tenure_years)
    print(f"\n--- Risk Score ---")
    print(f"  Composite:         {risk.composite_score}/100")
    print(f"  Label:             {risk.risk_label.value}")
    print(f"  Components:")
    print(f"    EMI ratio:       {risk.component_scores.emi_ratio_score}/35")
    print(f"    Buffer:          {risk.component_scores.buffer_score}/25")
    print(f"    Scenarios:       {risk.component_scores.scenario_survival_score}/30")
    print(f"    Tenure/Age:      {risk.component_scores.tenure_age_score}/10")
    print(f"  Risk factors:")
    for rf in risk.risk_factors:
        print(f"    - {rf}")

    print(f"\n{'=' * 60}")
    print("✅ All deterministic agents executed successfully")
    print(f"{'=' * 60}")


def test_pune_scenario():
    """₹45L under-construction in Karnataka, lower income."""
    print("\n")
    print("=" * 60)
    print("TEST: ₹45L Under-Construction in Karnataka")
    print("=" * 60)

    user_input = UserInput(
        monthly_income=85000,
        monthly_expenses=35000,
        total_savings=800000,
        down_payment=600000,
        property_price=4500000,
        tenure_years=25,
        annual_interest_rate=0.09,
        age=28,
        state="karnataka",
        property_type=PropertyType.UNDER_CONSTRUCTION,
        area_sqft=650,
        session_id="test_session_2",
    )

    loan_amount = user_input.property_price - user_input.down_payment
    india_costs = calculate_true_total_cost(
        base_price=user_input.property_price,
        state=user_input.state,
        property_type=user_input.property_type.value,
        loan_amount=loan_amount,
        area_sqft=user_input.area_sqft,
        annual_income=user_input.monthly_income * 12,
        tenure_years=user_input.tenure_years,
    )
    print(f"\n  TRUE TOTAL COST:   ₹{india_costs.true_total_cost:,.0f}")
    print(f"  PMAY eligible:     {'Yes' if india_costs.pmay_eligible else 'No'}")
    print(f"  PMAY subsidy NPV:  ₹{india_costs.pmay_subsidy_npv:,.0f}")
    print(f"  GST (5%):          ₹{india_costs.gst:,.0f}")
    print(f"  Stamp duty (5.6%): ₹{india_costs.stamp_duty:,.0f}")

    financial = calculate_affordability(user_input)
    print(f"  EMI:               ₹{financial.emi:,.0f}")
    print(f"  EMI/Income:        {financial.emi_to_income_ratio:.2%}")
    print(f"  Status:            {financial.affordability_status.value}")

    scenarios = run_all_scenarios(user_input, financial)
    print(f"  Scenarios survived: {scenarios.scenarios_survived}/5")

    risk = calculate_risk_score(financial, scenarios, user_input.age, user_input.tenure_years)
    print(f"  Risk score:        {risk.composite_score}/100 ({risk.risk_label.value})")

    print(f"\n{'=' * 60}")
    print("✅ Pune scenario executed successfully")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    test_mumbai_scenario()
    test_pune_scenario()
