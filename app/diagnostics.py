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


@router.get("/database", dependencies=[Depends(_require_api_key)])
def database_diagnostic() -> dict[str, object]:
    """Verify the application's configured database connection using a read-only query only."""
    try:
        from app.database import connection

        with connection() as conn:
            row = conn.execute("SELECT 1 AS connection_test, current_database() AS database_name").fetchone()
        if not row or row.get("connection_test") != 1:
            raise RuntimeError("Database probe returned an unexpected result.")
        return {
            "ok": True,
            "database": "connected",
            "query": "read_only_select_1",
            "database_name": row["database_name"],
            "side_effects": {"data_modified": False, "pinterest_called": False, "ai_generation_called": False},
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection check failed. Verify DATABASE_URL and Neon availability.",
        ) from None


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
    # Avoid billable generation/upload if critical read-only connectivity checks fail.
    prerequisites_ok = bool(checks.get("database", {}).get("ok") and checks.get("pinterest", {}).get("ok"))
    if prerequisites_ok:
        try:
            media = generate_and_host_pin_image(product_name=payload.product_name, product_details=payload.product_details)
            checks["cloudflare_image_generation_and_upload"] = {
                "ok": bool(media.get("image_url")),
                "model": media.get("model"),
                "uploaded": True,
                "image_id_returned": bool(media.get("image_id")),
            }
            if not media.get("image_url"):
                overall_ok = False
        except ImageGenerationError as exc:
            checks["cloudflare_image_generation_and_upload"] = {"ok": False, "error": str(exc)[:180]}
            overall_ok = False
        except Exception:
            checks["cloudflare_image_generation_and_upload"] = {"ok": False, "error": "image_generation_or_upload_failed"}
            overall_ok = False
    else:
        checks["cloudflare_image_generation_and_upload"] = {
            "ok": False, "skipped": True, "error": "database_or_pinterest_check_failed",
        }

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
