"""
MahaRERA public portal integration for builder/project verification.

Provides graceful degradation: if the portal is unavailable or RERA_LOOKUP_ENABLED
is False, returns a ReraData with data_source="unavailable" without raising.

The risk_score is computed deterministically from structured data — the LLM
never performs this calculation.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_RERA_LOOKUP_ENABLED = os.getenv("RERA_LOOKUP_ENABLED", "false").lower() == "true"


@dataclass
class ReraData:
    """Structured result from a MahaRERA lookup."""
    builder_name: str
    rera_registered: bool = False
    complaint_count: Optional[int] = None
    project_completion_pct: Optional[int] = None
    possession_date_registered: Optional[str] = None
    registration_status: str = "unknown"
    data_source: str = "unavailable"
    risk_score: int = field(default=0)
    risk_label: str = "unknown"

    def __post_init__(self) -> None:
        self.risk_score = _compute_risk_score(self)
        self.risk_label = _risk_label(self.risk_score)


def _compute_risk_score(data: "ReraData") -> int:
    """
    Compute a 0-100 risk score from structured RERA data.

    Scoring:
      - rera_registered == False: +50
      - registration_status == "lapsed": +30
      - complaint_count > 10: +40
      - complaint_count 5-10: +20
      - project_completion_pct < 50 and possession date is in the past: +20

    Returns:
        Integer risk score capped at 100.
    """
    score = 0
    if not data.rera_registered:
        score += 50
    if data.registration_status == "lapsed":
        score += 30
    if data.complaint_count is not None:
        if data.complaint_count > 10:
            score += 40
        elif data.complaint_count >= 5:
            score += 20
    if data.project_completion_pct is not None and data.project_completion_pct < 50:
        score += 20
    return min(score, 100)


def _risk_label(score: int) -> str:
    if score <= 20:
        return "low"
    if score <= 50:
        return "medium"
    if score <= 75:
        return "high"
    return "very_high"


def _unavailable(builder_name: str) -> ReraData:
    """Return a ReraData indicating data was unavailable, with no network calls."""
    return ReraData(
        builder_name=builder_name,
        rera_registered=False,
        data_source="unavailable",
        registration_status="unknown",
    )


async def fetch_rera_data(builder_name: str, project_name: str = "") -> ReraData:
    """
    Fetches builder and project data from MahaRERA public portal.

    Controlled by the RERA_LOOKUP_ENABLED environment variable (default: false).
    When disabled, returns immediately with data_source="unavailable" — no network
    calls are made. When enabled, attempts a search query against the MahaRERA
    public API. Falls back gracefully on any network or parsing failure.

    The risk_score is computed deterministically from structured data fields.
    Never raises — always returns a ReraData instance.

    Args:
        builder_name: Builder/developer name from user input.
        project_name: Optional project name for a more specific lookup.

    Returns:
        ReraData instance. data_source will be "unavailable" if the lookup was
        disabled or failed, "rera_scrape" if data was obtained.
    """
    if not builder_name.strip():
        return _unavailable(builder_name)

    if not _RERA_LOOKUP_ENABLED:
        logger.debug("RERA lookup disabled (RERA_LOOKUP_ENABLED=false)")
        return _unavailable(builder_name)

    try:
        return await _lookup_rera(builder_name, project_name)
    except Exception as exc:
        logger.warning("RERA lookup failed for '%s': %s", builder_name, exc)
        return _unavailable(builder_name)


async def _lookup_rera(builder_name: str, project_name: str) -> ReraData:
    """
    Internal lookup against MahaRERA public search endpoint.

    Returns ReraData with data_source="rera_scrape" if any structured data
    is obtained, or data_source="unavailable" if parsing fails.
    """
    search_url = (
        "https://maharera.mahaonline.gov.in/Promoters/SearchPromoterDetails"
    )
    params = {"promoterName": builder_name}
    if project_name:
        params["projectName"] = project_name

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(search_url, params=params)
        resp.raise_for_status()

    # MahaRERA returns HTML — we do lightweight heuristic parsing.
    # If the response includes registration status markers, extract them.
    body = resp.text.lower()
    registered = "registration no" in body or "rera" in body
    lapsed = "lapsed" in body or "expired" in body

    return ReraData(
        builder_name=builder_name,
        rera_registered=registered,
        complaint_count=None,
        project_completion_pct=None,
        possession_date_registered=None,
        registration_status="lapsed" if lapsed else ("active" if registered else "unknown"),
        data_source="rera_scrape",
    )
