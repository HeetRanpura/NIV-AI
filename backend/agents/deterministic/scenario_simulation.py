"""
Scenario Simulation Agent — Five stress-test scenarios.
Each scenario reruns financial math with modified inputs. No AI. Deterministic.
"""
from schemas.schemas import (
    UserInput, FinancialRealityOutput, AllScenariosOutput,
    ScenarioOutput, ScenarioSeverity
)
from agents.deterministic.financial_reality import _calculate_emi


def _simulate_scenario(
    scenario_name: str,
    description: str,
    user_input: UserInput,
    financial_reality: FinancialRealityOutput,
    income_modifier: float = 1.0,
    rate_bump: float = 0.0,
    job_loss_months: int = 0,
    emergency_expense: float = 0.0,
) -> ScenarioOutput:
    """
    Simulates a single financial scenario over 24 months.
    Returns survivability, buffer months, breaking point, and severity.
    """
    monthly_income = user_input.monthly_income * income_modifier
    monthly_expenses = user_input.monthly_expenses
    loan_amount = financial_reality.loan_amount

    # Recalculate EMI if interest rate changed
    if rate_bump > 0:
        modified_emi = _calculate_emi(
            loan_amount,
            user_input.annual_interest_rate + rate_bump,
            user_input.tenure_years,
        )
    else:
        modified_emi = financial_reality.emi

    # Start from savings after down payment, minus any emergency
    current_savings = (user_input.total_savings - user_input.down_payment) - emergency_expense

    breaking_point_month = None

    for month in range(1, 25):
        if job_loss_months > 0 and month <= job_loss_months:
            # Zero income during job loss, but expenses and EMI still due
            surplus = 0 - monthly_expenses - modified_emi
        else:
            surplus = monthly_income - monthly_expenses - modified_emi

        current_savings += surplus

        if current_savings <= 0 and breaking_point_month is None:
            breaking_point_month = month

    survivable = breaking_point_month is None
    buffer_months = (breaking_point_month - 1) if breaking_point_month else 24

    # Monthly shortfall calculation
    if job_loss_months > 0:
        monthly_shortfall = monthly_expenses + modified_emi
    else:
        net = monthly_income - monthly_expenses - modified_emi
        monthly_shortfall = abs(net) if net < 0 else None

    # Severity classification
    if survivable:
        severity = ScenarioSeverity.LOW
    elif buffer_months >= 6:
        severity = ScenarioSeverity.MEDIUM
    elif buffer_months >= 3:
        severity = ScenarioSeverity.HIGH
    else:
        severity = ScenarioSeverity.CRITICAL

    return ScenarioOutput(
        scenario_name=scenario_name,
        survivable=survivable,
        buffer_months=buffer_months,
        monthly_shortfall=round(monthly_shortfall, 2) if monthly_shortfall else None,
        breaking_point_month=breaking_point_month,
        severity=severity,
        description=description,
        modified_emi=round(modified_emi, 2),
        modified_monthly_income=round(monthly_income, 2) if job_loss_months == 0 else 0.0,
    )


def run_all_scenarios(
    user_input: UserInput,
    financial_reality: FinancialRealityOutput,
) -> AllScenariosOutput:
    """
    Runs five deterministic stress-test scenarios.
    Each scenario modifies inputs and simulates 24 months of cash flow.
    """
    base_case = _simulate_scenario(
        "Base Case",
        "Assumes stable conditions with no income or interest rate shocks.",
        user_input, financial_reality,
    )

    income_drop = _simulate_scenario(
        "Income Drop 30%",
        "Assumes your household income permanently drops by 30%.",
        user_input, financial_reality,
        income_modifier=0.7,
    )

    job_loss = _simulate_scenario(
        "Job Loss (6 Months)",
        "Assumes complete loss of income for 6 months while EMI obligations remain.",
        user_input, financial_reality,
        job_loss_months=6,
    )

    rate_hike = _simulate_scenario(
        "Interest Rate +2%",
        "Assumes your home loan interest rate increases by 200 basis points.",
        user_input, financial_reality,
        rate_bump=0.02,
    )

    emergency = _simulate_scenario(
        "Emergency Expense ₹5L",
        "Assumes an immediate emergency wiping ₹5 Lakhs from savings.",
        user_input, financial_reality,
        emergency_expense=500000.0,
    )

    scenarios = [base_case, income_drop, job_loss, rate_hike, emergency]
    survived = sum(1 for s in scenarios if s.survivable)

    return AllScenariosOutput(
        base_case=base_case,
        income_drop_30pct=income_drop,
        job_loss_6_months=job_loss,
        interest_rate_hike_2pct=rate_hike,
        emergency_expense_5L=emergency,
        scenarios_survived=survived,
    )
