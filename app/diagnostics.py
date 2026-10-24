"""Authenticated live integration diagnostics; never publishes a Pinterest Pin."""
from __future__ import annotations

import hmac
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


class DiagnosticRunInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(default="Kitchen spice rack organizer", min_length=1, max_length=300)
    product_details: str = Field(default="A practical organizer for spices in a home kitchen.", min_length=1, max_length=1000)


@router.post("/run", dependencies=[Depends(_require_api_key)])
def run_live_diagnostics(payload: DiagnosticRunInput) -> dict[str, object]:
    """Verify live dependencies. Image test uploads one public Cloudflare image and may incur provider usage."""
    from app.database import connection
    from app.credential_vault import get_pinterest_credential
    from app.media_generation import ImageGenerationError, generate_and_host_pin_image
    from app.content_generation import generate_pin_content

    checks: dict[str, object] = {}
    overall_ok = True

    try:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = {"ok": True, "check": "read_only_select_1"}
    except Exception:
        checks["database"] = {"ok": False, "error": "database_connection_or_query_failed"}
        overall_ok = False

    try:
        credential = get_pinterest_credential(payload.account_id)
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = client.get(
                f"{settings.pinterest_api_base_url.rstrip('/')}/user_account",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
            )
        checks["pinterest"] = {"ok": response.is_success, "check": "stored_credential_user_account_read", "http_status": response.status_code}
        if not response.is_success:
            overall_ok = False
    except LookupError:
        checks["pinterest"] = {"ok": False, "error": "credential_not_connected"}
        overall_ok = False
    except Exception:
        checks["pinterest"] = {"ok": False, "error": "credential_decryption_or_request_failed"}
        overall_ok = False

    media = None
    try:
        media = generate_and_host_pin_image(product_name=payload.product_name, product_details=payload.product_details)
        checks["cloudflare_image_generation_and_upload"] = {
            "ok": bool(media.get("image_url")),
            "model": media.get("model"),
            "uploaded": True,
            "image_id_returned": bool(media.get("image_id")),
        }
    except ImageGenerationError as exc:
        checks["cloudflare_image_generation_and_upload"] = {"ok": False, "error": str(exc)[:180]}
        overall_ok = False
    except Exception:
        checks["cloudflare_image_generation_and_upload"] = {"ok": False, "error": "image_generation_or_upload_failed"}
        overall_ok = False

    if media and settings.llm_api_key:
        try:
            generated, model_id = generate_pin_content(
                product_name=payload.product_name,
                product_details=payload.product_details,
                image_url=media["image_url"],
            )
            ok = bool(generated.title and generated.description and generated.alt_text)
            checks["deepseek_multimodal_generation"] = {
                "ok": ok, "model": model_id,
                "title_returned": bool(generated.title),
                "description_returned": bool(generated.description),
                "alt_text_returned": bool(generated.alt_text),
            }
            overall_ok = overall_ok and ok
        except Exception:
            checks["deepseek_multimodal_generation"] = {"ok": False, "error": "deepseek_multimodal_completion_failed"}
            overall_ok = False
    else:
        checks["deepseek_multimodal_generation"] = {"ok": False, "error": "llm_key_missing_or_image_generation_failed"}
        overall_ok = False

    return {
        "ok": overall_ok,
        "checks": checks,
        "side_effects": {
            "pinterest_pin_created": False,
            "pinterest_board_created": False,
            "product_persisted": False,
            "cloudflare_test_image_uploaded": bool(media),
            "provider_usage_may_be_billable": True,
        },
        "secrets_returned": False,
    }
