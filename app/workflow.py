"""Authenticated end-to-end product-to-Pinterest publishing workflow."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.content_generation import ContentGenerationError, GeneratedContent, generate_pin_content
from app.credential_vault import get_pinterest_credential
from app.database import (
    begin_publish_attempt, create_product_with_content_version,
    finish_publish_attempt, get_product_by_idempotency_key,
    reserve_workflow_generation, save_workflow_generation_image,
    save_workflow_generation_content, release_workflow_generation,
    complete_workflow_generation,
)
from app.media_generation import ImageGenerationError, generate_pin_image
from app.pinterest import image_media_source
from app.publishing_gateway import publish_pin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workflow", tags=["end-to-end"])

def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


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


def _release_generation_lease_safely(idempotency_key: str, lease_token: str) -> None:
    """Best-effort cleanup that never masks the original workflow failure."""
    try:
        release_workflow_generation(idempotency_key=idempotency_key, lease_token=lease_token)
    except Exception as exc:
        logger.error(
            "workflow stage=generation_lease_release outcome=failed exception_type=%s",
            type(exc).__name__,
        )


def _pinterest_request(method: str, path: str, token: str, *, body: dict | None = None) -> tuple[int, dict]:
    if method.upper() == "POST" and path.split("?", 1)[0].rstrip("/") == "/pins":
        raise HTTPException(
            status_code=400,
            detail="Pinterest Pin creation is only allowed through the canonical publication-ledger gateway.",
        )
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


def _ensure_board(token: str, name: str, description: str = "") -> str:
    """Resolve an existing owned board only; this workflow never creates boards."""
    _, response = _pinterest_request("GET", "/boards?page_size=100", token)
    seen: set[str] = set()
    for page_number in range(100):
        if not isinstance(response, dict):
            raise HTTPException(status_code=502, detail="Pinterest returned an invalid board-list response.")
        items = response.get("items", [])
        for board in items if isinstance(items, list) else []:
            if isinstance(board, dict) and board.get("name", "").casefold() == name.casefold() and board.get("id"):
                return str(board["id"])
        bookmark = response.get("bookmark")
        if not isinstance(bookmark, str) or not bookmark:
            break
        if bookmark in seen:
            raise HTTPException(status_code=502, detail="Pinterest returned a repeated board pagination cursor; board verification stopped.")
        seen.add(bookmark)
        if page_number == 99:
            raise HTTPException(status_code=503, detail="Pinterest board list exceeded the safe verification limit; no board was created.")
        from urllib.parse import urlencode
        _, response = _pinterest_request("GET", f"/boards?{urlencode({'page_size': 100, 'bookmark': bookmark})}", token)
    raise HTTPException(status_code=422, detail="The requested Pinterest board does not exist on this connected account. Create it in Pinterest, then retry; this workflow does not create boards.")


@router.post("/publish-product", dependencies=[Depends(_require_api_key)])
def publish_product_end_to_end(
    payload: ProductWorkflowInput,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200),
) -> dict[str, object]:
    """Reserve provider work, checkpoint reusable outputs, persist, then publish one Pin."""
    request_fingerprint = hashlib.sha256(json.dumps({
        "product_name": payload.product_name,
        "product_details": payload.product_details,
        "affiliate_url": payload.affiliate_url,
        "account_id": payload.account_id,
        "board_name": payload.board_name,
        "board_description": payload.board_description,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    try:
        existing = get_product_by_idempotency_key(idempotency_key)
    except Exception as exc:
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
        _, account_data = _pinterest_request("GET", "/user_account", credential["access_token"])
    except HTTPException as exc:
        raise HTTPException(
            status_code=503 if exc.status_code >= 500 else 401,
            detail="Stored Pinterest credential could not be verified. Reconnect the account before publishing.",
        ) from exc
    actual_user_id = account_data.get("id") if isinstance(account_data, dict) else None
    expected_user_id = credential.get("pinterest_user_id")
    if (not isinstance(actual_user_id, (str, int))
            or not expected_user_id
            or str(actual_user_id) != str(expected_user_id)
            or payload.account_id != f"pinterest:{expected_user_id}"):
        raise HTTPException(status_code=409, detail="Stored Pinterest credential identity does not match the requested account; no Pin publish request was sent.")

    token = credential["access_token"]
    # Resolve the destination before invoking billable providers or consuming the
    # idempotency key. A board/API failure must not leave an orphaned product row
    # that makes a safe retry impossible.
    try:
        board_id = _ensure_board(token, payload.board_name, payload.board_description)
    except HTTPException as exc:
        logger.error("workflow stage=board_resolution outcome=failed http_status=%s", exc.status_code)
        raise
    except Exception as exc:
        logger.error("workflow stage=board_resolution outcome=failed exception_type=%s", type(exc).__name__)
        raise

    # Acquire a durable cross-process lease before any billable provider call.
    # Provider outputs are checkpointed so a later-stage retry can reuse them.
    lease_token = str(uuid.uuid4())
    try:
        reservation = reserve_workflow_generation(
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            lease_token=lease_token,
        )
    except ValueError as exc:
        if str(exc) == "idempotency_key_payload_mismatch":
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with different workflow input.") from None
        raise
    except Exception as exc:
        logger.error("workflow stage=generation_reservation outcome=failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not reserve workflow generation; no billable provider was called.") from exc

    if not reservation["acquired"]:
        if reservation["status"] == "persisted":
            raise HTTPException(status_code=409, detail="This Idempotency-Key has already been persisted; inspect its product/publication record.")
        raise HTTPException(status_code=409, detail={
            "code": "workflow_generation_in_progress",
            "message": "Another request owns the generation lease for this Idempotency-Key. Retry after its lease expires or completes.",
        }, headers={"Retry-After": "30"})

    media = None
    if reservation.get("image_data_url"):
        media = {"image_url": reservation["image_data_url"], "model": reservation["image_model"]}
    else:
        try:
            media = generate_pin_image(
                product_name=payload.product_name,
                product_details=payload.product_details,
            )
            save_workflow_generation_image(
                idempotency_key=idempotency_key, lease_token=lease_token,
                image_data_url=media["image_url"], image_model=media["model"],
            )
        except ImageGenerationError as exc:
            _release_generation_lease_safely(idempotency_key, lease_token)
            logger.error("workflow stage=image_generation outcome=failed detail=%s", str(exc)[:180])
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            _release_generation_lease_safely(idempotency_key, lease_token)
            logger.error("workflow stage=image_checkpoint outcome=failed exception_type=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Image generation/checkpoint failed; retry with the same Idempotency-Key.") from exc

    if reservation.get("generated_content"):
        try:
            generated = GeneratedContent.model_validate(reservation["generated_content"])
            model_id = reservation["content_model"]
        except Exception as exc:
            _release_generation_lease_safely(idempotency_key, lease_token)
            logger.error("workflow stage=cached_content_validation outcome=failed exception_type=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Cached generated content is invalid; lease released. Retry with the same Idempotency-Key after the checkpoint is repaired.") from exc
    else:
        try:
            generated, model_id = generate_pin_content(
                product_name=payload.product_name,
                product_details=payload.product_details,
                image_url=media["image_url"],
            )
            save_workflow_generation_content(
                idempotency_key=idempotency_key, lease_token=lease_token,
                generated_content={
                    "pin_idea": generated.pin_idea, "title": generated.title,
                    "description": generated.description, "alt_text": generated.alt_text,
                }, content_model=model_id,
            )
        except ContentGenerationError as exc:
            _release_generation_lease_safely(idempotency_key, lease_token)
            logger.error("workflow stage=content_generation outcome=failed detail=%s", str(exc)[:180])
            raise HTTPException(status_code=503, detail="Content generation failed; the saved image will be reused on retry with the same Idempotency-Key.") from exc
        except Exception as exc:
            _release_generation_lease_safely(idempotency_key, lease_token)
            logger.error("workflow stage=content_checkpoint outcome=failed exception_type=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Content generation/checkpoint failed; retry with the same Idempotency-Key.") from exc

    try:
        product, content = create_product_with_content_version(
            product_name=payload.product_name,
            product_details=payload.product_details,
            image_url=None,
            affiliate_url=payload.affiliate_url,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            lease_token=lease_token,
            provider="deepseek",
            model_id=model_id,
            prompt_version="pin-content-v1",
            pin_idea=generated.pin_idea,
            title=generated.title,
            description=generated.description,
            alt_text=generated.alt_text,
        )
    except ValueError as exc:
        _release_generation_lease_safely(idempotency_key, lease_token)
        if str(exc) == "idempotency_key_payload_mismatch":
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with different workflow input.") from None
        raise
    except Exception as exc:
        logger.error("workflow stage=product_content_persistence outcome=failed exception_type=%s", type(exc).__name__)
        _release_generation_lease_safely(idempotency_key, lease_token)
        raise HTTPException(status_code=503, detail="Atomic product/content persistence failed; no Pinterest Pin was intentionally published. Cached provider outputs remain available for retry with the same Idempotency-Key.") from exc

    result = publish_pin(
        product_id=product["id"], content_version_id=content["id"],
        board_id=board_id, account_id=payload.account_id,
        access_token=token, title=content["title"],
        description=content["description"], alt_text=content["alt_text"],
        media_source=image_media_source(media["image_url"]),
        destination_url=payload.affiliate_url,
    )
    if result.get("already_published"):
        return {
            **result,
            "image_source": "pinterest_base64" if media["image_url"].startswith("data:") else "image_url",
        }
    saved_http_status = result.get("http_status")


    return {
        "published": True, "already_published": False, "pin_id": result["pin_id"],
        "board_id": board_id, "product_id": product["id"], "content_version_id": content["id"],
        "title": generated.title, "description": generated.description, "alt_text": generated.alt_text,
        "image_source": "pinterest_base64" if media["image_url"].startswith("data:") else "image_url", "affiliate_url": payload.affiliate_url,
        "provider": "DeepSeek", "model": model_id, "image_model": media["model"],
        "http_status": saved_http_status,
    }
