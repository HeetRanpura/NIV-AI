"""
Firebase Auth token verification middleware for FastAPI.
Extracts Firebase JWT from Authorization header, returns user uid.
Used as a dependency in every protected route.
"""
import os
from typing import Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

security = HTTPBearer(auto_error=False)


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def _skip_auth_enabled() -> bool:
    enabled = os.getenv("SKIP_AUTH", "false").lower() == "true"
    if enabled and _is_production():
        raise HTTPException(
            status_code=500,
            detail="SKIP_AUTH cannot be enabled in production",
        )
    return enabled


def _dev_uid_from_token(token: Optional[str]) -> str:
    if not token:
        return "dev-user"
    return token.split("-")[-1]


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    FastAPI dependency that verifies a Firebase ID token.

    Dev 3 sends the token in every request header as:
        Authorization: Bearer <firebase_id_token>

    Returns:
        The user's uid (str).

    Raises:
        HTTPException 401 if token is missing, invalid, or expired.
    """
    if _skip_auth_enabled():
        token = credentials.credentials if credentials else None
        return _dev_uid_from_token(token)

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    try:
        decoded = auth.verify_id_token(credentials.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


def verify_websocket_token(token: str) -> str:
    """Verify auth for websocket connections using the query token."""
    if _skip_auth_enabled():
        return _dev_uid_from_token(token)

    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
