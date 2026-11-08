"""Shared fail-closed service API-key authentication."""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Require a configured and matching service API key; never fail open."""
    if not settings.app_api_key:
        raise HTTPException(status_code=503, detail="API authentication is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")
