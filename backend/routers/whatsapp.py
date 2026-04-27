"""
WhatsApp webhook endpoints for NIV AI Concierge.

GET  /api/v1/whatsapp/webhook — webhook verification (Meta challenge-response)
POST /api/v1/whatsapp/webhook — incoming message handler

Controlled by WHATSAPP_ENABLED env var. Returns 200 OK for all POST requests
regardless of WHATSAPP_ENABLED to prevent Meta from disabling the webhook.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from pydantic import BaseModel
from typing import Optional

from backend.integrations.whatsapp_bot import VERIFY_TOKEN, handle_incoming_message, send_whatsapp_message, format_verdict_message, WHATSAPP_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")


_ENV = os.getenv("ENVIRONMENT", "development").lower()

def _verify_meta_signature(body: bytes, signature_header: str) -> bool:
    if not WHATSAPP_APP_SECRET:
        if _ENV == "production":
            logger.error("WHATSAPP_APP_SECRET not set in production — rejecting all webhook requests")
            return False
        logger.warning("WHATSAPP_APP_SECRET not set — skipping signature check (dev mode only)")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.HMAC(
        WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


class SendReportRequest(BaseModel):
    phone_number: str
    report: dict
    share_url: Optional[str] = ""


@router.post("/whatsapp/send", include_in_schema=True)
async def send_report_to_whatsapp(body: SendReportRequest):
    """
    Sends a formatted report summary to a phone number via WhatsApp.
    Accepts a 10-or-12 digit phone string (e.g. 919876543210 or 9876543210).
    """
    if not WHATSAPP_ENABLED:
        raise HTTPException(status_code=503, detail="WhatsApp is not enabled on this server.")
    phone = body.phone_number.strip().replace("+", "").replace(" ", "")
    if not phone.isdigit() or len(phone) < 10:
        raise HTTPException(status_code=422, detail="Invalid phone number format.")
    if len(phone) == 10:
        phone = "91" + phone
    msg = format_verdict_message(body.report, body.share_url or "")
    success = await send_whatsapp_message(phone, msg)
    if not success:
        raise HTTPException(status_code=502, detail="WhatsApp message could not be delivered. Check server credentials.")
    return {"status": "sent", "to": phone[:4] + "XXXXXX" + phone[-2:]}


@router.get("/whatsapp/webhook", include_in_schema=True)
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    """
    Meta webhook verification. Responds to hub.challenge when verify token matches.

    Args:
        hub_mode: Must be 'subscribe' for verification.
        hub_verify_token: Must match WHATSAPP_VERIFY_TOKEN env var.
        hub_challenge: Challenge string to echo back.

    Returns:
        Plain text hub_challenge on success, 403 on failure.
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully")
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed — token mismatch")


@router.post("/whatsapp/webhook", include_in_schema=True)
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Receives incoming WhatsApp messages from Meta webhook.
    Processes messages in background tasks to return 200 immediately.
    Meta requires sub-5-second webhook response time.

    Args:
        request: FastAPI request with Meta webhook payload.
        background_tasks: FastAPI background task runner.

    Returns:
        Always {"status": "ok"} — Meta retries on non-200 responses.
    """
    try:
        raw_body = await request.body()
        sig = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_meta_signature(raw_body, sig):
            logger.warning("WhatsApp webhook signature mismatch — request rejected")
            return {"status": "ok"}  # Always 200 to Meta, but process nothing
        payload = await request.json()
        entry = payload.get("entry", [])
        for e in entry:
            for change in e.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    phone = msg.get("from", "")
                    msg_type = msg.get("type", "")
                    if msg_type == "text" and phone:
                        text = msg.get("text", {}).get("body", "")
                        if text:
                            background_tasks.add_task(handle_incoming_message, phone, text)
    except Exception as exc:
        logger.warning("WhatsApp webhook parse failed: %s", exc)
    return {"status": "ok"}
