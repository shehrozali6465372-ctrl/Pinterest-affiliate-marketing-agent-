"""Authenticated read-only diagnostics; no Pin publishing or AI generation."""
from __future__ import annotations

import hmac

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


@router.get("/pinterest", dependencies=[Depends(_require_api_key)])
def pinterest_read_only_diagnostic() -> dict[str, object]:
    """Verify the stored Pinterest token with a read-only account request only."""
    try:
        from app.credential_vault import get_pinterest_credential

        account_id = "pinterest:1069323642682526567"
        credential = get_pinterest_credential(account_id)
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = client.get(
                f"{settings.pinterest_api_base_url.rstrip('/')}/user_account",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
            )
        return {
            "ok": response.is_success,
            "check": "stored_credential_user_account_read",
            "http_status": response.status_code,
            "side_effects": {
                "database_modified": False,
                "pinterest_pin_created": False,
                "pinterest_board_created": False,
                "ai_generation_called": False,
                "image_generation_called": False,
            },
        }
    except LookupError:
        return {
            "ok": False,
            "error": "credential_not_connected",
            "side_effects": {
                "database_modified": False,
                "pinterest_pin_created": False,
                "pinterest_board_created": False,
                "ai_generation_called": False,
                "image_generation_called": False,
            },
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Pinterest read-only credential check failed. Verify the stored credential and API access.",
        ) from None
