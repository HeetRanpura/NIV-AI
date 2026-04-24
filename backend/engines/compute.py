"""
Headless Compute Engine — All deterministic math in one function call.

compute_all() runs every deterministic agent in sequence and returns the
complete bundled result. This is the function behind the /api/v1/calculate
endpoint — designed for sub-50ms execution with zero LLM involvement.

Use cases:
    - Frontend real-time sliders that update as the user drags
    - Comparison tools that need fast recalculation
    - Batch processing without burning API quota
    - Unit testing the math pipeline in isolation
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schemas.schemas import UserInput, ComputeAllOutput
from engines.india_defaults import calculate_true_total_cost
from agents.deterministic.financial_reality import calculate_affordability
from agents.deterministic.scenario_simulation import run_all_scenarios
from agents.deterministic.risk_scorer import calculate_risk_score


def compute_all(user_input: UserInput) -> ComputeAllOutput:
    """
    Run every deterministic calculation and return the bundled result.

    Execution order (respects dependencies):
        1. india_defaults   — hidden cost breakdown (independent)
        2. affordability    — EMI, ratios, cash flow (independent)
        3. scenarios        — stress tests (depends on #2)
        4. risk_score       — composite score (depends on #2 and #3)

    Total execution time target: < 50ms on a single CPU core.
    All functions are pure Python arithmetic with no I/O.
    """
    loan_amount = user_input.property_price - user_input.down_payment
    if loan_amount < 0:
        loan_amount = 0.0

    india_costs = calculate_true_total_cost(
        base_price=user_input.property_price,
        state=user_input.state,
        property_type=user_input.property_type.value,
        loan_amount=loan_amount,
        area_sqft=user_input.area_sqft if user_input.area_sqft else 1000,
        area_sqm=user_input.area_sqm,
        district=user_input.district,
        is_female_buyer=user_input.is_female_buyer,
    )

    financial_reality = calculate_affordability(user_input)
    all_scenarios = run_all_scenarios(user_input, financial_reality)
    risk_score = calculate_risk_score(
        financial_reality=financial_reality,
        all_scenarios=all_scenarios,
        age=user_input.age,
        tenure_years=user_input.tenure_years,
    )

    return ComputeAllOutput(
        india_cost_breakdown=india_costs,
        financial_reality=financial_reality,
        all_scenarios=all_scenarios,
        risk_score=risk_score,
    )
