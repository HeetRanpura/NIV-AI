"""Output models for Niv AI decision reports."""
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    SAFE = "safe"
    RISKY = "risky"
    RECONSIDER = "reconsider"


class StressScenario(BaseModel):
    name: str
    description: str
    can_survive: bool
    months_before_default: Optional[float] = None
    key_number: str
    mitigation: str = ""
    severity: str = "medium"


class PropertyFlag(BaseModel):
    flag: str
    severity: str
    detail: str


class AssumptionChallenge(BaseModel):
    assumption: str
    challenge: str
    impact: str
    severity: str


class RentVsBuy(BaseModel):
    equivalent_monthly_rent: float = 0
    buying_monthly_cost: float = 0
    premium_for_ownership_pct: float = 0
    break_even_years: float = 0


class DecisionReport(BaseModel):
    verdict: Verdict
    confidence_score: int = Field(ge=1, le=10)
    verdict_reason: str
    top_reasons: list[str]
    financial_summary: dict
    stress_scenarios: list[StressScenario]
    property_assessment: dict
    assumptions_challenged: list[AssumptionChallenge]
    blind_spots: list[str]
    emotional_flags: list[str]
    conditions_for_safety: list[str]
    recommended_actions: list[str]
    rent_vs_buy: RentVsBuy
    computed_numbers: dict[str, Any]
    full_reasoning: str
    data_sources: list[str]
    limitations: list[str]
    disclaimer: str = (
        "This analysis is for informational purposes only. "
        "Not financial advice. Consult a qualified financial advisor."
    )
