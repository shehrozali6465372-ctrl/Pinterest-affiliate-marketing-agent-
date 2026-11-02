"""Single publication-ledger orchestration for every Pinterest Pin route."""
from __future__ import annotations

from typing import Any

from app.database import begin_publish_attempt, finish_publish_attempt
from app.pinterest import PinterestPublishError, create_pin_request


class PublicationConflict(RuntimeError):
    """An earlier attempt already owns this content-version/board pair."""

    def __init__(self, attempt: dict[str, Any]):
        super().__init__("A previous publication attempt exists; inspect its stored status before retrying.")
        self.attempt = attempt


class PublicationPersistenceError(RuntimeError):
    """The publication outcome could not be safely persisted."""


def publish_pin_with_ledger(
    *,
    product_id: int,
    content_version_id: int,
    board_id: str,
    account_id: str,
    access_token: str,
    payload: dict[str, object],
    reserved_attempt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reserve, publish once, and persist the outcome through one shared path.

    A pending/unknown/succeeded row is never retried. Provider transport and 5xx
    failures remain unknown, so callers must reconcile rather than retry blindly.
    """
    attempt = reserved_attempt or begin_publish_attempt(
        product_id=product_id,
        content_version_id=content_version_id,
        board_id=board_id,
        account_id=account_id,
    )
    if reserved_attempt is not None and (
        reserved_attempt.get("blocked")
        or reserved_attempt.get("status") != "pending"
        or reserved_attempt.get("product_id") != product_id
        or reserved_attempt.get("content_version_id") != content_version_id
        or reserved_attempt.get("board_id") != board_id
        or reserved_attempt.get("account_id") != account_id
    ):
        raise PublicationConflict(reserved_attempt)
    if attempt.get("blocked"):
        if attempt.get("account_mismatch"):
            raise PublicationConflict(attempt)
        if attempt.get("status") == "succeeded":
            return {
                "published": True,
                "already_published": True,
                "pin_id": attempt.get("pinterest_pin_id"),
                "publication_id": attempt["id"],
                "board_id": board_id,
                "http_status": attempt.get("http_status"),
            }
        raise PublicationConflict(attempt)

    try:
        http_status, response = create_pin_request(access_token=access_token, payload=payload)
    except PinterestPublishError as exc:
        try:
            finish_publish_attempt(
                attempt["id"],
                status="unknown" if exc.outcome_uncertain else "failed",
                http_status=exc.http_status,
                error_code=exc.error_code,
                response_metadata={},
            )
        except Exception as persist_exc:
            raise PublicationPersistenceError(
                "Pinterest request failed and its outcome could not be persisted; reconcile before retrying."
            ) from persist_exc
        raise

    pin_id = response["id"]
    metadata = {
        "id": pin_id,
        "board_id": response.get("board_id") if isinstance(response.get("board_id"), str) else board_id,
        "created_at": response.get("created_at") if isinstance(response.get("created_at"), str) else None,
    }
    try:
        saved = finish_publish_attempt(
            attempt["id"],
            status="succeeded",
            pinterest_pin_id=pin_id,
            http_status=http_status,
            response_metadata=metadata,
        )
    except Exception as exc:
        # Pinterest may already have created the Pin. Keep the ledger blocked.
        try:
            finish_publish_attempt(
                attempt["id"], status="unknown", http_status=http_status,
                error_code="publish_recording_error", response_metadata=metadata,
            )
        except Exception:
            pass
        raise PublicationPersistenceError(
            "Pinterest created a Pin but the success record could not be confirmed; reconcile before retrying."
        ) from exc

    return {
        "published": True,
        "already_published": False,
        "pin_id": saved["pinterest_pin_id"],
        "publication_id": saved["id"],
        "board_id": board_id,
        "http_status": saved.get("http_status", http_status),
        "response_metadata": metadata,
    }
