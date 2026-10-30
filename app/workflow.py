"""Authenticated end-to-end product-to-Pinterest publishing workflow."""
from __future__ import annotations

import hmac
import logging
import re
from uuid import uuid4
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.content_generation import ContentGenerationError, generate_pin_content
from app.credential_vault import get_pinterest_credential
from app.database import (
    begin_publish_attempt, create_product_with_content_version,
    finish_publish_attempt, get_product_by_idempotency_key,
)
from app.media_generation import ImageGenerationError, generate_and_host_pin_image
from app.pinterest import image_media_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["end-to-end"])

def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


def _log_workflow_failure(stage: str, exc: Exception, request_id: str, *, http_status: int | None = None) -> None:
    """Log safe failure classification without exception messages or request data."""
    diagnostic = getattr(exc, "diag", None)
    sqlstate = getattr(exc, "sqlstate", None) or "unknown"
    table_name = getattr(diagnostic, "table_name", None) or "unknown"
    column_name = getattr(diagnostic, "column_name", None) or "unknown"
    constraint_name = getattr(diagnostic, "constraint_name", None) or "unknown"
    logger.error(
        "workflow stage=%s outcome=failed request_id=%s exception_type=%s http_status=%s "
        "sqlstate=%s table=%s column=%s constraint=%s",
        stage, request_id, type(exc).__name__, http_status if http_status is not None else "unknown",
        sqlstate, table_name, column_name, constraint_name,
    )


class ProductWorkflowInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    affiliate_url: str = Field(min_length=8, max_length=4096)
    account_id: str = Field(min_length=1, max_length=200)
    board_name: str = Field(default="Modern Living Hub | Kitchen & Home Organization", min_length=1, max_length=100)
    board_description: str = Field(default="Kitchen organization, practical home finds, and home decor inspiration.", max_length=500)

    @field_validator("product_name", "product_details", "board_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("affiliate_url")
    @classmethod
    def valid_destination(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("affiliate_url must be a valid absolute HTTP(S) URL without embedded credentials or surrounding whitespace")
        return value


def _pinterest_request(method: str, path: str, token: str, *, body: dict | None = None) -> tuple[int, dict]:
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.request(
                method, f"{settings.pinterest_api_base_url.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
        payload = response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Pinterest request failed; verify the account before retrying any publish operation.") from exc
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=f"Pinterest API rejected the operation (HTTP {response.status_code}).")
    return response.status_code, payload


def _ensure_board(token: str, name: str, description: str) -> str:
    _, response = _pinterest_request("GET", "/boards?page_size=100", token)
    items = response.get("items", []) if isinstance(response, dict) else []
    for board in items:
        if isinstance(board, dict) and board.get("name", "").casefold() == name.casefold() and board.get("id"):
            return str(board["id"])
    _, created = _pinterest_request("POST", "/boards", token, body={"name": name, "description": description})
    board_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(board_id, str) or not board_id:
        raise HTTPException(status_code=502, detail="Pinterest did not return a board ID; board creation was not confirmed.")
    return board_id


@router.post("/publish-product", dependencies=[Depends(_require_api_key)])
def publish_product_end_to_end(
    payload: ProductWorkflowInput,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID", max_length=128),
) -> dict[str, object]:
    """Generate image and copy before persisting, then publish one Pin."""
    request_id = re.sub(r"[^A-Za-z0-9_.:-]", "_", x_request_id or str(uuid4()))[:128]
    try:
        existing = get_product_by_idempotency_key(idempotency_key)
    except Exception as exc:
        _log_workflow_failure("idempotency_state_read", exc, request_id, http_status=503)
        raise HTTPException(status_code=503, detail="Could not verify idempotency state; refusing to start a potentially duplicate workflow.") from exc
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "idempotency_key_reused",
                "message": "This Idempotency-Key has already been accepted. Check the existing product/publication record; use a new key only for a genuinely new Pin.",
                "product_id": existing["id"],
            },
        )
    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected in the credential vault.") from exc

    # Validate the stored OAuth token before invoking billable image/LLM providers.
    try:
        _pinterest_request("GET", "/user_account", credential["access_token"])
    except HTTPException as exc:
        _log_workflow_failure("pinterest_credential_verification", exc, request_id, http_status=exc.status_code)
        raise HTTPException(
            status_code=503 if exc.status_code >= 500 else 401,
            detail="Stored Pinterest credential could not be verified. Reconnect the account before publishing.",
        ) from exc

    token = credential["access_token"]
    # Resolve the destination before invoking billable providers or consuming the
    # idempotency key. A board/API failure must not leave an orphaned product row
    # that makes a safe retry impossible.
    try:
        board_id = _ensure_board(token, payload.board_name, payload.board_description)
    except HTTPException as exc:
        _log_workflow_failure("board_resolution", exc, request_id, http_status=exc.status_code)
        raise
    except Exception as exc:
        _log_workflow_failure("board_resolution", exc, request_id)
        raise

    # Generate both external-provider outputs before consuming the persisted key.
    # A transient DeepSeek failure therefore leaves no product row behind and the
    # same Idempotency-Key remains retryable.
    try:
        media = generate_and_host_pin_image(
            product_name=payload.product_name,
            product_details=payload.product_details,
        )
    except ImageGenerationError as exc:
        _log_workflow_failure("image_generation", exc, request_id, http_status=503)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        generated, model_id = generate_pin_content(
            product_name=payload.product_name,
            product_details=payload.product_details,
            image_url=media["image_url"],
        )
    except ContentGenerationError as exc:
        _log_workflow_failure("content_generation", exc, request_id, http_status=503)
        raise HTTPException(status_code=503, detail="Content generation failed before product persistence; retry with the same Idempotency-Key.") from exc

    try:
        product, content = create_product_with_content_version(
            product_name=payload.product_name,
            product_details=payload.product_details,
            image_url=None,
            affiliate_url=payload.affiliate_url,
            idempotency_key=idempotency_key,
            provider="deepseek",
            model_id=model_id,
            prompt_version="pin-content-v1",
            pin_idea=generated.pin_idea,
            title=generated.title,
            description=generated.description,
            alt_text=generated.alt_text,
        )
    except Exception as exc:
        # psycopg exposes structured diagnostics for constraint failures. These
        # fields identify schema drift (for example a NOT NULL column) without
        # logging SQL, parameters, product data, credentials, or provider output.
        _log_workflow_failure("product_content_persistence", exc, request_id, http_status=503)
        raise HTTPException(status_code=503, detail="Atomic product/content persistence failed; no Pinterest Pin was intentionally published. If the transaction rolled back, retry with the same Idempotency-Key; otherwise inspect the stored product before retrying.") from exc

    try:
        attempt = begin_publish_attempt(
            product_id=product["id"], content_version_id=content["id"],
            board_id=board_id, account_id=payload.account_id,
        )
    except Exception as exc:
        _log_workflow_failure("publication_attempt_create", exc, request_id, http_status=503)
        raise HTTPException(status_code=503, detail="Publication attempt could not be recorded; no Pinterest Pin was sent. Inspect the product record before retrying.") from exc
    if attempt.get("blocked"):
        if attempt.get("status") == "succeeded":
            return {
                "published": True, "already_published": True,
                "pin_id": attempt.get("pinterest_pin_id"), "board_id": board_id,
                "product_id": product["id"], "content_version_id": content["id"],
                "image_source": "pinterest_base64" if media["image_url"].startswith("data:") else "image_url",
            }
        raise HTTPException(status_code=409, detail="A previous publish attempt is pending or uncertain. Check the Pinterest board before retrying.")

    body = {
        "board_id": board_id, "title": generated.title, "description": generated.description,
        "alt_text": generated.alt_text,
        "media_source": image_media_source(media["image_url"]),
        "link": payload.affiliate_url,
    }
    try:
        http_status, result = _pinterest_request("POST", "/pins", token, body=body)
        pin_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(pin_id, str) or not pin_id:
            finish_publish_attempt(attempt["id"], status="unknown", http_status=http_status, error_code="missing_pin_id", response_metadata={})
            raise HTTPException(status_code=502, detail="Pinterest returned no Pin ID; outcome is uncertain. Verify the board before retrying.")
        saved = finish_publish_attempt(
            attempt["id"], status="succeeded", pinterest_pin_id=pin_id,
            http_status=http_status,
            response_metadata={"id": pin_id, "board_id": board_id, "created_at": result.get("created_at")},
        )
    except HTTPException as exc:
        _log_workflow_failure("pinterest_pin_publish", exc, request_id, http_status=exc.status_code)
        try:
            if exc.status_code >= 500:
                finish_publish_attempt(attempt["id"], status="unknown", error_code="pinterest_outcome_uncertain", response_metadata={})
            else:
                finish_publish_attempt(attempt["id"], status="failed", http_status=exc.status_code, error_code="pinterest_request_rejected", response_metadata={})
        except Exception:
            pass
        raise
    except Exception as exc:
        _log_workflow_failure("pinterest_publish_recording", exc, request_id, http_status=502)
        try:
            finish_publish_attempt(attempt["id"], status="unknown", error_code="publish_recording_error", response_metadata={})
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Publish outcome may be uncertain; check Pinterest before retrying.") from exc

    return {
        "published": True, "already_published": False, "pin_id": saved["pinterest_pin_id"],
        "board_id": board_id, "product_id": product["id"], "content_version_id": content["id"],
        "title": generated.title, "description": generated.description, "alt_text": generated.alt_text,
        "image_source": "pinterest_base64" if media["image_url"].startswith("data:") else "image_url", "affiliate_url": payload.affiliate_url,
        "provider": "DeepSeek", "model": model_id, "image_model": media["model"],
        "http_status": saved["http_status"],
    }
