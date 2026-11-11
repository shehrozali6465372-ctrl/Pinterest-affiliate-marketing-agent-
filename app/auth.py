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

 
def require_credential_ingest_key(
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> None:
    """Require the separately scoped trusted-Hub service credential; fail closed on misconfiguration."""
    expected = settings.pinterest_credential_ingest_key
    if not expected:
        raise HTTPException(status_code=503, detail="Credential-ingest authentication is not configured.")
    if not x_credential_ingest_key or not hmac.compare_digest(x_credential_ingest_key, expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")
