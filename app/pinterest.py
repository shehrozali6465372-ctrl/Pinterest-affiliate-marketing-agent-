"""Real Pinterest API v5 publishing client.

No success is returned unless Pinterest confirms a Pin ID. Ambiguous outcomes are
marked unknown by the caller so the system does not blindly retry and duplicate Pins.
"""
from __future__ import annotations

import httpx

from app.config import settings


class PinterestPublishError(RuntimeError):
    """Error during publish, with explicit certainty about external side effects."""

    def __init__(
        self,
        message: str,
        *,
        outcome_uncertain: bool,
        http_status: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain
        self.http_status = http_status
        self.error_code = error_code


def publish_image_pin(
    *,
    board_id: str,
    title: str,
    description: str,
    alt_text: str,
    image_url: str,
    affiliate_url: str,
) -> dict[str, object]:
    """Publish a Pin to the configured account and return verified response metadata."""
    if not settings.pinterest_access_token:
        raise PinterestPublishError(
            "PINTEREST_ACCESS_TOKEN is not configured.",
            outcome_uncertain=False,
            error_code="missing_access_token",
        )
    if not board_id.strip():
        raise PinterestPublishError(
            "PINTEREST_BOARD_ID is not configured.",
            outcome_uncertain=False,
            error_code="missing_board_id",
        )

    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins"
    payload = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "alt_text": alt_text,
        # This is the real user-provided product image, not a synthetic substitute.
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
            "is_standard": True,
        },
        # Pass the affiliate destination unchanged, including tracking parameters.
        "link": affiliate_url,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {settings.pinterest_access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.RequestError as exc:
        raise PinterestPublishError(
            "Pinterest request outcome is uncertain; do not retry blindly.",
            outcome_uncertain=True,
            error_code="transport_outcome_unknown",
        ) from exc

    if response.status_code >= 400:
        # A definite 4xx is a rejected request. A 5xx can be ambiguous: the service
        # might have created the Pin before returning an error.
        uncertain = response.status_code >= 500
        raise PinterestPublishError(
            "Pinterest rejected the request." if not uncertain
            else "Pinterest returned a server error; the outcome may be uncertain.",
            outcome_uncertain=uncertain,
            http_status=response.status_code,
            error_code=f"pinterest_http_{response.status_code}",
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise PinterestPublishError(
            "Pinterest returned a non-JSON response; the publish outcome is uncertain.",
            outcome_uncertain=True,
            http_status=response.status_code,
            error_code="invalid_provider_response",
        ) from exc

    pin_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(pin_id, str) or not pin_id.strip():
        raise PinterestPublishError(
            "Pinterest did not return a Pin ID; the publish outcome is uncertain.",
            outcome_uncertain=True,
            http_status=response.status_code,
            error_code="missing_pin_id",
        )

    # Store only minimal response metadata; never persist the access token or arbitrary body.
    metadata = {
        "id": pin_id,
        "board_id": body.get("board_id") if isinstance(body.get("board_id"), str) else board_id,
        "created_at": body.get("created_at") if isinstance(body.get("created_at"), str) else None,
    }
    return {"pin_id": pin_id, "http_status": response.status_code, "metadata": metadata}
