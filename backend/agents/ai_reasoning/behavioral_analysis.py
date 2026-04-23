"""
BehavioralAnalysisAgent — Detects cognitive and emotional biases from the
user's behavioral questionnaire answers and financial inputs.

Key improvement over original:
    Each bias flag now includes a financial_impact field with specific rupee
    amounts so Marcus, Zara, and Soren can reference concrete numbers during
    the roundtable discussion instead of giving generic behavioral observations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from schemas.schemas import BehavioralAnalysisOutput, BiasFlagItem, BiasType, BiasSeverity


SYSTEM_PROMPT = """
You are a behavioral psychologist specialising in financial decision-making
for Indian households.

You analyse how people describe their home buying situation and identify
cognitive and emotional biases. You are calm, observational, and non-judgmental.

Your most important rule: every bias flag you identify must connect directly
to a specific rupee amount or financial ratio from the data provided.
Never give a generic implication like "this could lead to financial stress."
Instead say exactly which number is at risk and by how much.

You always respond in valid JSON matching the exact format requested.
CRITICAL: Your entire response must be a single JSON object. Nothing outside the JSON.
"""


class BehavioralAnalysisAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="BehavioralAnalysis",
            persona="Behavioral psychologist who identifies financial decision biases and maps them to rupee risk",
            system_prompt=SYSTEM_PROMPT
        )

    async def analyze(
        self,
        behavioral_answers: list,
        financial_inputs: dict,
        india_cost_breakdown: dict
    ) -> BehavioralAnalysisOutput:
        context = self._build_context(
            behavioral_answers, financial_inputs, india_cost_breakdown
        )
        prompt = self._build_analysis_prompt(context)
        raw = await self.call(prompt)
        return self._parse_output(raw)

    # -------------------------------------------------------------------------
    # Context builder
    # -------------------------------------------------------------------------

    def _build_context(
        self,
        behavioral_answers: list,
        financial_inputs: dict,
        india_cost_breakdown: dict
    ) -> dict:
        """
        Build the context dict passed to the LLM.
        Pre-calculates the EMI, ratio, and monthly surplus here in Python
        so the agent can reference exact numbers without doing math itself.
        LLMs should never do arithmetic — we give them the answers.
        """
        monthly_income = financial_inputs.get("monthly_income", 0)
        monthly_expenses = financial_inputs.get("monthly_expenses", 0)
        property_price = financial_inputs.get("property_price", 0)
        down_payment = financial_inputs.get("down_payment", 0)
        annual_rate = financial_inputs.get("annual_interest_rate", 0.085)
        tenure_years = financial_inputs.get("tenure_years", 20)
        total_savings = financial_inputs.get("total_savings", 0)

        loan_amount = max(property_price - down_payment, 0)

        # Calculate EMI using standard amortization formula
        # This is the same formula used in financial_reality.py
        emi = 0.0
        if loan_amount > 0 and annual_rate > 0:
            r = annual_rate / 12
            n = tenure_years * 12
            power = (1 + r) ** n
            emi = loan_amount * r * power / (power - 1)

        emi_to_income_ratio = emi / monthly_income if monthly_income > 0 else 0
        monthly_surplus = monthly_income - monthly_expenses - emi
        savings_after_down_payment = total_savings - down_payment
        true_total_cost = india_cost_breakdown.get("true_total_cost", property_price)
        cost_gap = true_total_cost - total_savings

        # Wrap user-provided free-text answers in XML delimiters to prevent
        # prompt injection. The question and bias_signal fields are system-
        # controlled so only the answer field needs sandboxing.
        sanitized_answers = []
        for answer in behavioral_answers:
            sanitized = dict(answer)
            if "answer" in sanitized:
                sanitized["answer"] = (
                    f"<buyer_notes>{sanitized['answer']}</buyer_notes>"
                )
            sanitized_answers.append(sanitized)

        return {
            "behavioral_answers": sanitized_answers,
            "financial_inputs": {
                "monthly_income": monthly_income,
                "monthly_expenses": monthly_expenses,
                "total_savings": total_savings,
                "down_payment": down_payment,
                "property_price": property_price,
                "tenure_years": tenure_years,
                "annual_interest_rate": annual_rate,
                "age": financial_inputs.get("age"),
                "state": financial_inputs.get("state"),
            },
            "pre_calculated_numbers": {
                "loan_amount": round(loan_amount, 2),
                "emi_per_month": round(emi, 2),
                "emi_to_income_ratio_percent": round(emi_to_income_ratio * 100, 1),
                "monthly_surplus_after_emi": round(monthly_surplus, 2),
                "savings_remaining_after_down_payment": round(savings_after_down_payment, 2),
                "true_total_cost_including_hidden": round(true_total_cost, 2),
                "funding_gap_savings_vs_true_cost": round(cost_gap, 2),
                "months_of_expenses_covered_by_savings": round(
                    savings_after_down_payment / max(monthly_expenses + emi, 1), 1
                )
            }
        }

    # -------------------------------------------------------------------------
    # Prompt builder
    # -------------------------------------------------------------------------

    def _build_analysis_prompt(self, context: dict) -> str:
        return self.build_prompt(
            context=context,
            task="""
Analyse the behavioral questionnaire answers and financial inputs.
Identify all cognitive and emotional biases present.

The pre_calculated_numbers section gives you the exact financial figures.
Use these numbers directly in your implication and financial_impact fields.
Do not invent numbers — only use what is in pre_calculated_numbers.

For each bias found provide:
- bias_type: exactly one of: FOMO, overconfidence, anchoring, social_pressure,
  scarcity_bias, optimism_bias, denial
- severity: exactly one of: low, medium, high
- evidence: the exact quote or specific data point from the answers that
  triggered this flag — be specific, not generic
- implication: what financial risk does this bias create, referencing the
  exact rupee amounts from pre_calculated_numbers
- financial_impact: a single sentence stating the specific rupee amount or
  percentage at risk due to this bias. Example:
  "FOMO is pushing this buyer toward a ₹56,409/month EMI that is already
  37.6% of income — any income drop makes this unserviceable."

Also provide:
- behavioral_risk_score: overall score from 0 to 10 where 10 is highest risk
- recommended_questions: 2 to 3 follow-up questions to surface deeper bias
- summary: 2 to 3 sentence plain English behavioral profile
- emotionally_committed: true if user shows signs of already committing to
  a specific property

Respond in this exact JSON format:
{
    "bias_flags": [
        {
            "bias_type": "FOMO",
            "severity": "high",
            "evidence": "exact quote or data point here",
            "implication": "specific financial risk with rupee amounts here",
            "financial_impact": "single sentence with exact rupee amount at risk"
        }
    ],
    "behavioral_risk_score": 7.5,
    "recommended_questions": [
        "question 1",
        "question 2"
    ],
    "summary": "plain English summary here",
    "emotionally_committed": false
}
"""
        )

    # -------------------------------------------------------------------------
    # Output parser
    # -------------------------------------------------------------------------

    def _parse_output(self, raw: dict) -> BehavioralAnalysisOutput:
        """
        Parse the LLM response into a BehavioralAnalysisOutput.
        Handles bias_type normalisation so the model's varied naming
        conventions all map to the correct BiasType enum values.
        The financial_impact field is appended to implication if present
        so all downstream agents see the rupee context without needing
        a schema change.
        """
        valid_bias_types = {b.value for b in BiasType}

        # Map alternative names the model might use to the correct enum values
        bias_type_map = {
            "risk_blindness": "denial",
            "risk_aversion": "denial",
            "loss_aversion": "denial",
            "herd_mentality": "social_pressure",
            "peer_pressure": "social_pressure",
            "fear_of_missing_out": "FOMO",
            "fomo": "FOMO",
            "over_confidence": "overconfidence",
            "optimism": "optimism_bias",
            "scarcity": "scarcity_bias",
            "anchor": "anchoring",
            "anchoring_bias": "anchoring",
        }

        bias_flags = []
        for flag in raw.get("bias_flags", []):
            raw_type = flag.get("bias_type", "").lower().strip()

            if raw_type in valid_bias_types:
                mapped_type = raw_type
            elif raw_type.upper() in valid_bias_types:
                mapped_type = raw_type.upper()
            elif raw_type in bias_type_map:
                mapped_type = bias_type_map[raw_type]
            else:
                print(f"[BehavioralAnalysis] Unknown bias type '{raw_type}' — skipping")
                continue

            # Combine implication and financial_impact into a single rich
            # implication string so the roundtable agents have full context
            implication = flag.get("implication", "")
            financial_impact = flag.get("financial_impact", "")
            if financial_impact and financial_impact not in implication:
                implication = f"{implication} {financial_impact}".strip()

            try:
                bias_flags.append(
                    BiasFlagItem(
                        bias_type=BiasType(mapped_type),
                        severity=BiasSeverity(flag.get("severity", "low")),
                        evidence=flag.get("evidence", ""),
                        implication=implication
                    )
                )
            except Exception as e:
                print(f"[BehavioralAnalysis] Skipping bias flag due to error: {e}")
                continue

        return BehavioralAnalysisOutput(
            bias_flags=bias_flags,
            behavioral_risk_score=float(raw.get("behavioral_risk_score", 0.0)),
            recommended_questions=raw.get("recommended_questions", []),
            summary=raw.get("summary", ""),
            emotionally_committed=bool(raw.get("emotionally_committed", False))
        )