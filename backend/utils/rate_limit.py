"""
Shared rate limiter instance for Niv AI endpoints.

Import this in both main.py (for app.state wiring) and route modules (for decorators).
Avoids circular imports by keeping the limiter in a neutral utility module.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
