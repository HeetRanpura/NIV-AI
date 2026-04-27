"""Shared prompt hardening helpers for LLM agents."""
from __future__ import annotations


BIAS_CONTROL_SUFFIX = """

EVIDENCE AND FAIRNESS RULES — follow these strictly:
- Use only the provided facts, computed numbers, document text, and benchmark context.
- If evidence is missing, say it is missing. Do not guess or fabricate positives or negatives.
- Prioritize deterministic financial evidence over narrative tone or speculation.
- Do not infer risk from gender, marital status, religion, caste, ethnicity, or other non-financial identity traits.
- Do not penalize or favor a builder, area, or buyer unless explicit evidence is present in the prompt or cited benchmark/search context.
- Keep uncertainty separate from risk. Unknown information is not automatically negative.
- Keep recommendations symmetric, evidence-based, and proportional to the actual numbers.
""".strip()


def apply_bias_hardening(system_prompt: str) -> str:
    """Appends the shared evidence-first fairness rules to an agent system prompt."""
    base = (system_prompt or "").strip()
    if BIAS_CONTROL_SUFFIX in base:
        return base
    return f"{base}\n\n{BIAS_CONTROL_SUFFIX}".strip()
