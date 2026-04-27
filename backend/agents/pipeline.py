"""
Agent Pipeline — orchestrates all 6 agents with dependency-aware parallelism.
Single entry point: run_analysis(raw_input) -> report dict.

Execution order:
  Agent 1 (Context) → sequential, all others depend on it
  Agents 2 (Financial) + 4 (Property) → concurrent via asyncio.gather
  Agent 3 (Risk) → sequential after Agent 2 (needs financial verdict)
  Agent 5 (Assumption Challenger) → sequential after 2, 3, 4
  Agent 6 (Decision Composer) → sequential after all
"""
from __future__ import annotations
import asyncio
import logging
import time
from backend.agents import context_synthesizer, financial_analyst, risk_simulator
from backend.agents import property_analyst, assumption_challenger, decision_composer
from backend.calculations.benchmarks import get_maintenance_estimate, get_rental_yield, get_area_benchmark_result
from backend.calculations.financial import compute_all, find_path_to_safe
from backend.calculations.research_thresholds import get_triggered_research_stats
from backend.calculations.delta_engine import classify_financial_state, compute_survival_timeline
from backend.calculations.risk_engine import evaluate_risk, get_action_plan
from backend.calculations.bias_detector import detect_verdict_bias
from backend.llm.client import LLMClient

logger = logging.getLogger(__name__)


async def run_analysis(raw_input: dict) -> dict:
    try:
        return await asyncio.wait_for(_run_analysis_internal(raw_input), timeout=120.0)
    except asyncio.TimeoutError:
        logger.error("Pipeline timed out after 120s")
        raise RuntimeError("Analysis timed out. Please try again.")


async def _run_analysis_internal(raw_input: dict) -> dict:
    start = time.perf_counter()
    llm = LLMClient()
    fin = raw_input["financial"]
    prop = raw_input["property"]

    benchmark_result = get_area_benchmark_result(prop["location_area"])
    maintenance = benchmark_result.data.maintenance_typical if benchmark_result.data else 5.5
    rental_yield = benchmark_result.data.rental_yield_pct if benchmark_result.data else 2.5
    equivalent_rent = round(prop["property_price"] * (rental_yield / 100) / 12, 2)

    computed = compute_all(
        monthly_income=fin["monthly_income"], spouse_income=fin["spouse_income"],
        existing_emis=fin["existing_emis"], monthly_expenses=fin["monthly_expenses"],
        liquid_savings=fin["liquid_savings"], dependents=fin["dependents"],
        property_price=prop["property_price"], down_payment=prop["down_payment_available"],
        loan_tenure_years=prop["loan_tenure_years"], interest_rate=prop["expected_interest_rate"],
        carpet_area_sqft=prop["carpet_area_sqft"], buyer_gender=prop["buyer_gender"],
        is_ready_to_move=prop["is_ready_to_move"], maintenance_per_sqft=maintenance,
        equivalent_rent=equivalent_rent,
        commute_distance_km=prop.get("commute_distance_km", 0.0))
    computed_dict = computed.to_dict()

    financial_state = classify_financial_state(computed_dict)

    monthly_burn = (
        computed.monthly_ownership.total
        + fin["existing_emis"]
        + fin["monthly_expenses"]
    )
    survival_timeline = compute_survival_timeline(
        fin["monthly_income"] + fin["spouse_income"],
        monthly_burn,
        fin["liquid_savings"],
        computed_dict["post_purchase_savings"],
        computed_dict["monthly_emi"],
    )

    research_warnings = get_triggered_research_stats(computed_dict, raw_input)

    # Agent 1: Context Synthesizer — must complete first
    t1 = time.perf_counter()
    context = await context_synthesizer.run(llm, raw_input, computed_dict)
    logger.debug("Agent 1 (Context) done in %.2fs", time.perf_counter() - t1)

    stress_data = [{"name": s.name, "description": s.description, "can_survive": s.can_survive,
                    "months_before_default": s.months_before_default, "key_number": s.key_number,
                    "new_emi": s.new_emi, "new_ratio": s.new_ratio} for s in computed.stress_scenarios]

    # Phase A: Agents 2 + 4 concurrently (no cross-dependency between them)
    t2 = time.perf_counter()
    financial, property_result = await asyncio.gather(
        financial_analyst.run(llm, context, computed_dict, raw_input),
        property_analyst.run(llm, context, computed_dict, raw_input)
    )
    logger.debug("Agents 2+4 (Financial+Property) done in %.2fs", time.perf_counter() - t2)

    # Phase B: Agent 3 — needs Agent 2's financial verdict
    t3 = time.perf_counter()
    risk = await risk_simulator.run(llm, context, financial, computed_dict, stress_data, raw_input)
    logger.debug("Agent 3 (Risk) done in %.2fs", time.perf_counter() - t3)

    # Agent 5 — needs all of 2, 3, 4
    t5 = time.perf_counter()
    assumptions = await assumption_challenger.run(
        llm, context, financial, risk, property_result, computed_dict, raw_input,
        research_warnings=research_warnings)
    logger.debug("Agent 5 (Assumption Challenger) done in %.2fs", time.perf_counter() - t5)

    # Agent 6 — needs all previous
    t6 = time.perf_counter()
    output_language = raw_input.get("output_language", "english")
    verdict = await decision_composer.run(
        llm, context, financial, risk, property_result, assumptions, computed_dict, raw_input,
        output_language=output_language)
    final_llm_metadata = llm.get_last_call_metadata()
    logger.debug("Agent 6 (Decision Composer) done in %.2fs, total %.2fs",
                 time.perf_counter() - t6, time.perf_counter() - start)

    final_verdict = verdict.get("verdict", "risky")

    # Bias detection — ground truth check against deterministic math
    stress_passed_count = sum(1 for s in computed.stress_scenarios if s.can_survive)
    bias_result = detect_verdict_bias(
        llm_verdict=final_verdict,
        llm_confidence_score=verdict.get("confidence_score", 5),
        deterministic_state=financial_state,
        deterministic_confidence={},
        stress_passed=stress_passed_count,
        stress_total=len(computed.stress_scenarios),
    )
    if bias_result["verdict_was_corrected"] and bias_result["bias_score"] >= 60:
        logger.warning(
            "High bias detected (score=%d, type=%s) overriding %s → %s",
            bias_result["bias_score"], bias_result["bias_type"],
            final_verdict, bias_result["corrected_verdict"],
        )
        final_verdict = bias_result["corrected_verdict"]

    risk_eval = evaluate_risk(computed_dict, raw_input)
    action_plan = get_action_plan(risk_eval, computed_dict)

    # Path-to-safe reverse calculator — only when verdict is not safe
    base_params = {
        "monthly_income": fin["monthly_income"], "spouse_income": fin["spouse_income"],
        "existing_emis": fin["existing_emis"], "monthly_expenses": fin["monthly_expenses"],
        "liquid_savings": fin["liquid_savings"], "dependents": fin["dependents"],
        "property_price": prop["property_price"], "down_payment": prop["down_payment_available"],
        "loan_tenure_years": prop["loan_tenure_years"], "interest_rate": prop["expected_interest_rate"],
        "carpet_area_sqft": prop["carpet_area_sqft"], "buyer_gender": prop["buyer_gender"],
        "is_ready_to_move": prop["is_ready_to_move"], "maintenance_per_sqft": maintenance,
        "equivalent_rent": equivalent_rent, "commute_distance_km": prop.get("commute_distance_km", 0.0),
    }
    path_to_safe = None if final_verdict == "safe" else find_path_to_safe(base_params, final_verdict)

    rvb = property_result.get("rent_vs_buy", {})
    return {
        "verdict": final_verdict,
        "confidence_score": verdict.get("confidence_score", 5),
        "verdict_reason": verdict.get("verdict_reason", ""),
        "top_reasons": verdict.get("top_reasons", []),
        "financial_summary": financial,
        "stress_scenarios": risk.get("scenarios", []),
        "property_assessment": property_result,
        "assumptions_challenged": assumptions.get("challenges", []),
        "blind_spots": assumptions.get("blind_spots", []),
        "emotional_flags": assumptions.get("emotional_flags", []),
        "conditions_for_safety": verdict.get("conditions_for_safety", []),
        "recommended_actions": verdict.get("recommended_actions", []),
        "rent_vs_buy": {"equivalent_monthly_rent": rvb.get("equivalent_monthly_rent", equivalent_rent),
                        "buying_monthly_cost": rvb.get("buying_monthly_cost", computed.monthly_ownership.total),
                        "premium_for_ownership_pct": rvb.get("premium_for_ownership_pct", computed.rent_vs_buy.premium_pct),
                        "break_even_years": rvb.get("break_even_years", computed.rent_vs_buy.break_even_years)},
        "computed_numbers": computed_dict,
        "full_reasoning": verdict.get("full_reasoning", ""),
        "research_warnings": research_warnings,
        "path_to_safe": path_to_safe,
        "benchmark_coverage": {
            "area_used": benchmark_result.data.name if benchmark_result.data else prop["location_area"],
            "coverage_level": benchmark_result.coverage_level,
            "confidence_score": benchmark_result.confidence_score,
            "warning": benchmark_result.warning_message,
        },
        "financial_state": financial_state,
        "survival_timeline": survival_timeline,
        "bias_detection": bias_result,
        "risk_evaluation": risk_eval,
        "action_plan": action_plan,
        "data_sources": [
            "Mumbai micro-market benchmarks (NIV AI Q4 2025 database)",
            "RBI Master Circular — Housing Finance (2024)",
            "Maharashtra Stamp Duty & Registration Act",
            "Income Tax Act Sections 80C and 24(b)",
            "RERA Maharashtra Public Portal",
        ],
        "limitations": ["Legal title not verified", "Builder financials not assessed",
                        "Physical inspection not done", "Bank eligibility may differ",
                        "Benchmark data may lag market by 1-2 quarters"],
        "disclaimer": "This analysis is for informational purposes only. Not financial advice.",
        "_meta": {
            "pipeline_time_seconds": round(time.perf_counter() - start, 2),
            "final_llm": final_llm_metadata,
            "original_llm_verdict": verdict.get("verdict", "risky"),
        }
    }
