"""
Firebase Auth token verification middleware for FastAPI.
Extracts Firebase JWT from Authorization header, returns user uid.
Used as a dependency in every protected route.
"""
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

security = HTTPBearer()


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
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )
