"""Single controlled Pinterest Pin creation gateway.

All application routes that create Pins must delegate to this module. It owns
publication reservation, the sole Pinterest POST /pins call, and outcome recording.
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException

from app.config import settings
from app.pin_limits import validate_pin_text_fields


def publish_pin(
    *, product_id: int, content_version_id: int, board_id: str,
    account_id: str | None, access_token: str, title: str,
    description: str, alt_text: str, media_source: dict[str, object],
    destination_url: str, niche_id: int | None = None,
) -> dict[str, object]:
    """Reserve and create exactly one Pin, recording definite/uncertain outcomes."""
    from app.database import begin_publish_attempt, finish_publish_attempt

    try:
        validate_pin_text_fields(title=title, description=description, alt_text=alt_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{exc} No Pin publish request was sent.") from None
    if not access_token or not access_token.strip():
        raise HTTPException(status_code=503, detail="Pinterest access token is unavailable; no Pin publish request was sent.")
    if not board_id or not board_id.strip() or not account_id or not account_id.strip():
        raise HTTPException(status_code=422, detail="Pinterest account and board are required; no Pin publish request was sent.")
    if not isinstance(media_source, dict) or not media_source:
        raise HTTPException(status_code=422, detail="Pinterest media source is required; no Pin publish request was sent.")
    if not isinstance(destination_url, str) or not destination_url.strip():
        raise HTTPException(status_code=422, detail="Pinterest destination URL is required; no Pin publish request was sent.")
    if niche_id is not None and (
        isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0
    ):
        raise HTTPException(status_code=422, detail="niche_id must be a positive integer; no Pin publish request was sent.")

    try:
        reservation_kwargs = {
            "product_id": product_id,
            "content_version_id": content_version_id,
            "board_id": board_id,
            "account_id": account_id,
        }
        if niche_id is not None:
            reservation_kwargs["niche_id"] = niche_id
        attempt = begin_publish_attempt(**reservation_kwargs)
    except Exception:
        raise HTTPException(status_code=503, detail="Could not reserve publication ledger; no Pin publish request was sent.") from None

    if attempt.get("blocked"):
        if attempt.get("account_mismatch"):
            raise HTTPException(status_code=409, detail={
                "code": "publication_account_mismatch",
                "message": "An existing publication belongs to a different or unknown Pinterest account; it cannot be reused.",
            })
        if attempt.get("niche_attribution_mismatch"):
            raise HTTPException(status_code=409, detail={
                "code": "publication_niche_attribution_mismatch",
                "message": "This publication is already attributed to a different niche; attribution is immutable.",
            })
        if attempt.get("niche_attribution_missing"):
            raise HTTPException(status_code=409, detail={
                "code": "publication_niche_attribution_missing",
                "message": "This existing publication has no niche attribution and cannot be retroactively attributed.",
            })
        if attempt.get("niche_assignment_inactive"):
            raise HTTPException(status_code=409, detail={
                "code": "niche_assignment_inactive",
                "message": "The account profile, niche assignment or niche is no longer active; no Pin request was sent.",
            })
        if attempt.get("niche_account_not_connected"):
            raise HTTPException(status_code=409, detail={
                "code": "niche_account_not_connected",
                "message": "The Pinterest account is not connected; no Pin request was sent.",
            })
        if attempt.get("status") == "succeeded":
            return {
                "published": True, "already_published": True,
                "pin_id": attempt.get("pinterest_pin_id"),
                "publication_id": attempt.get("id"),
                "board_id": board_id, "product_id": product_id,
                "content_version_id": content_version_id,
            }
        raise HTTPException(status_code=409, detail={
            "code": "publication_not_retryable", "status": attempt.get("status"),
            "message": "A prior publish is pending or uncertain. Verify the Pinterest board before any retry.",
        })

    body = {
        "board_id": board_id, "title": title, "description": description,
        "alt_text": alt_text, "media_source": media_source,
        "link": destination_url,
    }
    base = settings.pinterest_api_base_url.rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = client.post(
                f"{base}/pins",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=body,
            )
    except httpx.RequestError:
        try:
            finish_publish_attempt(attempt["id"], status="unknown", error_code="transport_outcome_unknown")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Pinterest publish outcome is uncertain. Check the board; do not retry blindly.") from None

    try:
        result = response.json() if response.content else {}
    except ValueError:
        result = None

    if response.status_code >= 500:
        try:
            finish_publish_attempt(attempt["id"], status="unknown", http_status=response.status_code,
                                   error_code="pinterest_server_outcome_unknown")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Pinterest server response leaves publish outcome uncertain. Verify the board before retrying.")
    if not response.is_success:
        try:
            finish_publish_attempt(attempt["id"], status="failed", http_status=response.status_code,
                                   error_code="pinterest_request_rejected")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Pinterest rejected Pin creation (HTTP {response.status_code}).")

    pin_id = result.get("id") if isinstance(result, dict) else None
    if not isinstance(pin_id, str) or not pin_id.strip():
        try:
            finish_publish_attempt(attempt["id"], status="unknown", http_status=response.status_code,
                                   error_code="missing_pin_id")
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Pinterest returned no Pin ID; outcome is uncertain. Verify the board before retrying.")

    try:
        saved = finish_publish_attempt(
            attempt["id"], status="succeeded", pinterest_pin_id=pin_id,
            http_status=response.status_code,
            response_metadata={
                "id": pin_id, "board_id": board_id,
                "created_at": result.get("created_at") if isinstance(result.get("created_at"), str) else None,
            },
        )
    except Exception:
        # Pinterest may have created the Pin. Keep the reservation pending so
        # automatic retries remain blocked; recovery is an operator action.
        raise HTTPException(status_code=503, detail="Pinterest may have created the Pin, but the publication result could not be recorded. Do not retry; inspect and reconcile the publication.") from None

    return {
        "published": True, "already_published": False,
        "pin_id": saved["pinterest_pin_id"], "publication_id": saved["id"],
        "board_id": board_id, "product_id": product_id,
        "content_version_id": content_version_id,
        "http_status": saved.get("http_status", response.status_code),
    }
