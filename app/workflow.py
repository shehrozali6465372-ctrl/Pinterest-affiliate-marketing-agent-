"""Authenticated end-to-end product-to-Pinterest publishing workflow."""
from __future__ import annotations

import hmac
import logging
import re
from uuid import uuid4
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.config import settings
from app.content_generation import AFFILIATE_DISCLOSURE, ContentGenerationError, generate_pin_content
from app.credential_vault import get_pinterest_credential
from app.database import (
    begin_publish_attempt, create_product_with_content_version,
    finish_publish_attempt, get_product_by_idempotency_key,
)
from app.media_generation import ImageGenerationError, generate_and_host_pin_image
from app.pinterest import image_media_source
from app.pin_limits import PIN_DESCRIPTION_MAX_LENGTH, validate_pin_text_fields

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["end-to-end"])

def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


def _require_credential_ingest_key(
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> None:
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")


class HubPinPublishInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    board_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=PIN_DESCRIPTION_MAX_LENGTH)
    alt_text: str = Field(min_length=1, max_length=500)
    image_url: HttpUrl
    destination_url: str = Field(min_length=8, max_length=4096)

    @field_validator("account_id", "board_id", "title", "alt_text")
    @classmethod
    def required_values_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("destination_url")
    @classmethod
    def preserve_valid_destination(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("destination_url must be an absolute HTTP(S) URL without embedded credentials or surrounding whitespace")
        return value


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
    # Enforce Pinterest Pin text limits at the final outbound API boundary too.
    if method.upper() == "POST" and path == "/pins" and isinstance(body, dict):
        try:
            validate_pin_text_fields(
                title=body.get("title"),
                description=body.get("description"),
                alt_text=body.get("alt_text"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    """Resolve a board across all Pinterest pages before creating anything."""
    bookmark: str | None = None
    seen_bookmarks: set[str] = set()
    for _page in range(100):
        query = {"page_size": 100}
        if bookmark:
            query["bookmark"] = bookmark
        _, response = _pinterest_request("GET", f"/boards?{urlencode(query)}", token)
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Pinterest returned an invalid board-list response; refusing to create a possible duplicate.")
        items = response.get("items", [])
        if not isinstance(items, list):
            raise HTTPException(status_code=502, detail="Pinterest returned an invalid board list; refusing to create a possible duplicate.")
        for board in items:
            if isinstance(board, dict) and str(board.get("name") or "").casefold() == name.casefold() and board.get("id"):
                return str(board["id"])
        next_bookmark = response.get("bookmark")
        if not next_bookmark:
            break
        next_bookmark = str(next_bookmark)
        if next_bookmark in seen_bookmarks:
            raise HTTPException(status_code=502, detail="Pinterest repeated a board pagination cursor; refusing to create a possible duplicate.")
        seen_bookmarks.add(next_bookmark)
        bookmark = next_bookmark
    else:
        raise HTTPException(status_code=502, detail="Pinterest board pagination exceeded the safety limit; refusing to create a possible duplicate.")

    _, created = _pinterest_request("POST", "/boards", token, body={"name": name, "description": description})
    board_id = created.get("id") if isinstance(created, dict) else None
    if not isinstance(board_id, str) or not board_id:
        raise HTTPException(status_code=502, detail="Pinterest did not return a board ID; board creation was not confirmed.")
    return board_id


@router.post("/publish-hub-pin", dependencies=[Depends(_require_credential_ingest_key)])
def publish_hub_pin(
    payload: HubPinPublishInput,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    """Canonical Hub publishing gateway: enforce disclosure and persist the ledger before Pinterest writes."""
    from app.content_generation import PROMPT_VERSION
    from app.database import create_product_with_content_version

    description = payload.description.strip()
    if AFFILIATE_DISCLOSURE.casefold() not in description.casefold():
        description = f"{description}\n\n{AFFILIATE_DISCLOSURE}" if description else AFFILIATE_DISCLOSURE
    if len(description) > 2000:
        raise HTTPException(status_code=422, detail="Description exceeds the maximum length after required affiliate disclosure.")

    try:
        existing = get_product_by_idempotency_key(idempotency_key)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not verify the publication idempotency state; refusing to publish.") from exc
    if existing:
        raise HTTPException(status_code=409, detail={
            "code": "idempotency_key_reused",
            "message": "This request key was already accepted. Reconcile the existing product/publication before attempting another Pin.",
            "product_id": existing["id"],
        })

    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected in the credential vault.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Stored Pinterest credential could not be read.") from None

    # A 401 here occurs before any product or publication is created and before a Pin write.
    _pinterest_request("GET", "/user_account", credential["access_token"])

    try:
        product, content = create_product_with_content_version(
            product_name=payload.title,
            product_details=description,
            image_url=str(payload.image_url),
            affiliate_url=payload.destination_url,
            idempotency_key=idempotency_key,
            provider="hub_manual",
            model_id="user_supplied",
            prompt_version="hub-manual-v1",
            pin_idea=payload.title,
            title=payload.title,
            description=description,
            alt_text=payload.alt_text,
        )
        attempt = begin_publish_attempt(
            product_id=product["id"],
            content_version_id=content["id"],
            board_id=payload.board_id,
            account_id=payload.account_id,
        )
    except Exception as exc:
        _log_workflow_failure("hub_publication_persistence", exc, idempotency_key)
        raise HTTPException(status_code=503, detail="Could not persist the Hub publication and idempotency record; no Pin was intentionally sent.") from exc

    if attempt.get("blocked"):
        raise HTTPException(status_code=409, detail="A previous publication attempt exists; inspect its stored status before retrying.")

    body = {
        "board_id": payload.board_id,
        "title": payload.title,
        "description": description,
        "alt_text": payload.alt_text,
        "media_source": image_media_source(str(payload.image_url)),
        "link": payload.destination_url,
    }
    try:
        http_status, result = _pinterest_request("POST", "/pins", credential["access_token"], body=body)
        pin_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(pin_id, str) or not pin_id:
            finish_publish_attempt(attempt["id"], status="unknown", http_status=http_status, error_code="missing_pin_id", response_metadata={})
            raise HTTPException(status_code=502, detail="Pinterest returned no Pin ID; publication outcome is uncertain. Do not retry blindly.")
        saved = finish_publish_attempt(
            attempt["id"], status="succeeded", pinterest_pin_id=pin_id,
            http_status=http_status,
            response_metadata={"id": pin_id, "board_id": payload.board_id, "created_at": result.get("created_at")},
        )
    except HTTPException as exc:
        try:
            finish_publish_attempt(
                attempt["id"],
                status="unknown" if exc.status_code >= 500 else "failed",
                http_status=exc.status_code,
                error_code="pinterest_outcome_uncertain" if exc.status_code >= 500 else "pinterest_request_rejected",
                response_metadata={},
            )
        except Exception:
            pass
        raise
    except Exception as exc:
        try:
            finish_publish_attempt(attempt["id"], status="unknown", error_code="publish_recording_error", response_metadata={})
        except Exception:
            pass
        raise HTTPException(status_code=502, detail="Pin publication outcome may be uncertain; inspect Pinterest and the publication record before retrying.") from exc

    return {
        "published": True,
        "already_published": False,
        "pin_id": saved["pinterest_pin_id"],
        "product_id": product["id"],
        "content_version_id": content["id"],
        "board_id": payload.board_id,
        "title": payload.title,
        "description": description,
        "alt_text": payload.alt_text,
        "affiliate_url": payload.destination_url,
        "http_status": saved["http_status"],
    }


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
                "image_source": "image_base64",
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
        "image_source": "image_base64", "affiliate_url": payload.affiliate_url,
        "provider": "DeepSeek", "model": model_id, "image_model": media["model"],
        "http_status": saved["http_status"],
    }
