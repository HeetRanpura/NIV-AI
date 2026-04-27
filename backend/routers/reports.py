"""Reports endpoints — save, retrieve, list analysis reports, and record outcomes."""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from backend.firebase.firestore import get_report, get_report_age_days, list_reports, save_outcome, save_report
from backend.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["reports"])


class OutcomeRequest(BaseModel):
    """Request body for recording what the buyer actually decided."""
    outcome: str  # "bought" | "walked_away" | "still_deciding"
    follow_up_rating: Optional[int] = None  # 1–5, only meaningful for "bought"


@router.post("/reports")
async def create_report(body: dict, x_user_id: Optional[str] = Header(None)):
    user_id = x_user_id or "anonymous"
    report_data = body.get("report")
    if not report_data:
        raise HTTPException(status_code=422, detail="Missing report in body")
    doc_id = await save_report(user_id, report_data, body.get("input", {}))
    return {"id": doc_id, "saved": doc_id is not None}


@router.get("/reports")
async def get_reports(x_user_id: Optional[str] = Header(None), limit: int = 20):
    user_id = x_user_id or "anonymous"
    return {"reports": await list_reports(user_id, limit=min(limit, 50))}


@router.get("/reports/{report_id}")
@limiter.limit("60/minute")
async def get_single_report(request: Request, report_id: str, x_user_id: Optional[str] = Header(None)):
    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    owner = report.get("user_id", "anonymous")
    requester = x_user_id or "anonymous"
    if owner != "anonymous" and owner != requester and not report.get("is_shared"):
        raise HTTPException(status_code=403, detail="Access denied")
    return report


@router.post("/reports/{report_id}/outcome")
async def record_outcome(report_id: str, body: OutcomeRequest):
    """
    Records what decision the buyer actually made for a saved report.

    Used to build the proprietary outcome dataset for calibrating verdict accuracy.
    Stored anonymously — no PII collected.
    """
    valid_outcomes = {"bought", "walked_away", "still_deciding"}
    if body.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=422,
            detail=f"outcome must be one of: {', '.join(sorted(valid_outcomes))}",
        )

    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    age_days = await get_report_age_days(report_id)
    original_verdict = report.get("verdict", "unknown")

    success = await save_outcome(
        report_id=report_id,
        outcome=body.outcome,
        original_verdict=original_verdict,
        days_since_analysis=age_days or 0,
        follow_up_rating=body.follow_up_rating,
    )
    return {"recorded": success, "outcome": body.outcome}
