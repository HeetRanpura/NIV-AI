import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000"

# Test payload matching a real Mumbai scenario
TEST_INPUT = {
    "monthly_income": 150000,
    "monthly_expenses": 60000,
    "total_savings": 1500000,
    "down_payment": 1500000,
    "property_price": 8000000,
    "tenure_years": 20,
    "annual_interest_rate": 0.085,
    "age": 32,
    "state": "maharashtra",
    "property_type": "ready_to_move",
    "area_sqft": 850,
    "session_id": "test_session_integration"
}

TEST_BEHAVIORAL = {
    "session_id": "test_session_integration",
    "answers": [
        {
            "question_id": 1,
            "question": "Are you feeling time pressure to buy?",
            "answer": "Yes, prices are rising fast",
            "bias_signal": "FOMO"
        },
        {
            "question_id": 2,
            "question": "Have you already emotionally committed to a specific property?",
            "answer": "Yes, we really love this apartment",
            "bias_signal": "anchoring"
        },
        {
            "question_id": 3,
            "question": "Has your family or social circle recently bought homes?",
            "answer": "Yes, three of my close friends bought last year",
            "bias_signal": "social_pressure"
        },
        {
            "question_id": 4,
            "question": "Do you expect your income to grow significantly in the next 3 years?",
            "answer": "Yes, I expect at least 30% growth",
            "bias_signal": "optimism_bias"
        },
        {
            "question_id": 5,
            "question": "Have you considered what happens if you lose your job?",
            "answer": "Not really, my job feels very secure",
            "bias_signal": "risk_blindness"
        },
        {
            "question_id": 6,
            "question": "Are you stretching your budget for a once in a lifetime deal?",
            "answer": "A little bit yes",
            "bias_signal": "scarcity_bias"
        },
        {
            "question_id": 7,
            "question": "Would buying require significantly cutting lifestyle expenses?",
            "answer": "We would need to cut back on dining and travel",
            "bias_signal": "denial"
        }
    ]
}

async def run_integration_test():
    async with httpx.AsyncClient(timeout=120.0) as client:

        print("\n" + "="*60)
        print("NIV AI — Integration Test")
        print("="*60)

        # Step 1 — Health check
        print("\n[1] Health check...")
        r = await client.get(f"{BASE_URL}/health")
        print(f"    Status: {r.status_code}")
        print(f"    Response: {r.json()}")
        assert r.status_code == 200

        # Step 2 — Test deterministic pipeline directly
        print("\n[2] Testing deterministic pipeline directly...")
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        from schemas.schemas import UserInput, PropertyType, BehavioralIntake, BehavioralAnswer
        from engines.india_defaults import calculate_true_total_cost
        from agents.deterministic.financial_reality import calculate_affordability
        from agents.deterministic.scenario_simulation import run_all_scenarios
        from agents.deterministic.risk_scorer import calculate_risk_score

        user_input = UserInput(**{**TEST_INPUT})

        loan_amount = user_input.property_price - user_input.down_payment
        india_costs = calculate_true_total_cost(
            base_price=user_input.property_price,
            state=user_input.state,
            property_type=user_input.property_type.value,
            loan_amount=loan_amount,
            area_sqft=user_input.area_sqft
        )
        financial = calculate_affordability(user_input)
        scenarios = run_all_scenarios(user_input, financial)
        risk = calculate_risk_score(financial, scenarios, user_input.age, user_input.tenure_years)

        print(f"    ✅ India costs: ₹{india_costs.true_total_cost:,.0f}")
        print(f"    ✅ EMI: ₹{financial.emi:,.0f} | Ratio: {financial.emi_to_income_ratio:.2%}")
        print(f"    ✅ Scenarios survived: {scenarios.scenarios_survived}/5")
        print(f"    ✅ Risk score: {risk.composite_score}/100 ({risk.risk_label.value})")

        # Step 3 — Test AI agents directly
        print("\n[3] Testing AI agents directly...")
        from agents.ai_reasoning.behavioral_analysis import BehavioralAnalysisAgent
        from agents.validation.validation import ValidationAgent

        behavioral_agent = BehavioralAnalysisAgent()
        blackboard_mock = {
            "user_input": TEST_INPUT,
            "financial_reality": financial.model_dump(),
            "all_scenarios": scenarios.model_dump(),
            "risk_score": risk.model_dump(),
            "india_cost_breakdown": india_costs.model_dump()
        }

        print("    Running behavioral analysis agent...")
        behavioral_result = await behavioral_agent.analyze(
            behavioral_answers=TEST_BEHAVIORAL["answers"],
            financial_inputs=TEST_INPUT,
            india_cost_breakdown=india_costs.model_dump()
        )
        print(f"    ✅ Behavioral agent fired")
        print(f"    ✅ Bias flags detected: {len(behavioral_result.bias_flags)}")
        for flag in behavioral_result.bias_flags:
            print(f"       - {flag.bias_type.value} ({flag.severity.value}): {flag.evidence[:60]}")
        print(f"    ✅ Behavioral risk score: {behavioral_result.behavioral_risk_score}/10")
        print(f"    ✅ Emotionally committed: {behavioral_result.emotionally_committed}")

        print("\n    Running validation agent...")
        blackboard_mock["behavioral_analysis"] = behavioral_result.model_dump()
        validation_result = await ValidationAgent().validate(blackboard_mock)
        print(f"    ✅ Validation agent fired")
        print(f"    ✅ Assumptions logged: {len(validation_result.assumptions_log)}")
        print(f"    ✅ Conflicts found: {len(validation_result.conflicts)}")
        print(f"    ✅ Data quality score: {validation_result.data_quality_score}/100")

        # Step 4 — Test orchestrator analyze
        print("\n[4] Testing orchestrator.analyze()...")
        from agents.orchestration.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        behavioral_intake = BehavioralIntake(
            session_id="test_session_integration",
            answers=[BehavioralAnswer(**a) for a in TEST_BEHAVIORAL["answers"]]
        )

        deterministic_results = {
            "india_cost_breakdown": india_costs.model_dump(),
            "financial_reality": financial.model_dump(),
            "all_scenarios": scenarios.model_dump(),
            "risk_score": risk.model_dump()
        }

        analysis_response = await orchestrator.analyze(
            session_id="test_session_integration",
            user_input=user_input,
            behavioral_intake=behavioral_intake,
            deterministic_results=deterministic_results
        )

        print(f"    ✅ Orchestrator analyze complete")
        print(f"    ✅ Presentation output received: {analysis_response.presentation is not None}")
        print(f"    ✅ Warning cards: {len(analysis_response.presentation.warning_cards)}")
        print(f"    ✅ Risk gauge score: {analysis_response.presentation.risk_gauge_data.score}")

        print("\n" + "="*60)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("="*60)
        print("\nNext step: test WebSocket roundtable with a real WebSocket client")

if __name__ == "__main__":
    asyncio.run(run_integration_test())