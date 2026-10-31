"""Pinterest API v5 image publishing with URL and Base64 media sources."""
from __future__ import annotations
import base64
import re
from urllib.parse import quote
import httpx
from app.config import settings

class PinterestPublishError(RuntimeError):
    """Error during publish, with explicit certainty about external side effects."""
    def __init__(self, message: str, *, outcome_uncertain: bool, http_status: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain
        self.http_status = http_status
        self.error_code = error_code

def image_media_source(image_url: str) -> dict[str, object]:
    """Use image_base64 for a data URL, otherwise preserve legacy public image URLs."""
    if image_url.startswith("data:"):
        match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", image_url)
        if not match:
            raise PinterestPublishError("Generated image data URL is malformed; no Pinterest request was sent.", outcome_uncertain=False, error_code="invalid_image_data")
    else:
        return {"source_type": "image_url", "url": image_url, "is_standard": True}
    mime, encoded = match.groups()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise PinterestPublishError("Generated image data is invalid; no Pinterest request was sent.", outcome_uncertain=False, error_code="invalid_image_data") from exc
    if len(raw) < 1024:
        raise PinterestPublishError("Generated image data is unexpectedly small; no Pinterest request was sent.", outcome_uncertain=False, error_code="image_data_too_small")
    return {"source_type": "image_base64", "content_type": mime, "data": encoded, "is_standard": True}

def publish_image_pin(*, board_id: str, title: str, description: str, alt_text: str, image_url: str, affiliate_url: str) -> dict[str, object]:
    if not settings.pinterest_access_token:
        raise PinterestPublishError("PINTEREST_ACCESS_TOKEN is not configured.", outcome_uncertain=False, error_code="missing_access_token")
    if not board_id.strip():
        raise PinterestPublishError("PINTEREST_BOARD_ID is not configured.", outcome_uncertain=False, error_code="missing_board_id")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins"
    payload = {"board_id": board_id, "title": title, "description": description, "alt_text": alt_text, "media_source": image_media_source(image_url), "link": affiliate_url}
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.post(endpoint, headers={"Authorization": f"Bearer {settings.pinterest_access_token}", "Content-Type": "application/json"}, json=payload)
    except httpx.RequestError as exc:
        raise PinterestPublishError("Pinterest request outcome is uncertain; do not retry blindly.", outcome_uncertain=True, error_code="transport_outcome_unknown") from exc
    if response.status_code >= 400:
        uncertain = response.status_code >= 500
        raise PinterestPublishError("Pinterest rejected the request." if not uncertain else "Pinterest returned a server error; the outcome may be uncertain.", outcome_uncertain=uncertain, http_status=response.status_code, error_code=f"pinterest_http_{response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise PinterestPublishError("Pinterest returned a non-JSON response; the publish outcome is uncertain.", outcome_uncertain=True, http_status=response.status_code, error_code="invalid_provider_response") from exc
    pin_id = body.get("id") if isinstance(body, dict) else None
    if not isinstance(pin_id, str) or not pin_id.strip():
        raise PinterestPublishError("Pinterest did not return a Pin ID; the publish outcome is uncertain.", outcome_uncertain=True, http_status=response.status_code, error_code="missing_pin_id")
    metadata = {"id": pin_id, "board_id": body.get("board_id") if isinstance(body.get("board_id"), str) else board_id, "created_at": body.get("created_at") if isinstance(body.get("created_at"), str) else None}
    return {"pin_id": pin_id, "http_status": response.status_code, "metadata": metadata}


class PinterestReadError(RuntimeError):
    """A sanitized error from a read-only Pinterest verification request."""


def list_board_pins_read_only(
    *, board_id: str, access_token: str, page_size: int = 250, max_pages: int = 100,
) -> dict[str, object]:
    """Read every page of a Pinterest board; never creates or changes Pins.

    Pagination fails closed on malformed/repeated bookmarks or provider errors.
    The API host is derived only from configured Pinterest API base URL.
    """
    if not board_id or not board_id.strip():
        raise ValueError("board_id is required")
    if not access_token or not access_token.strip():
        raise ValueError("access_token is required")
    if not 1 <= page_size <= 250 or not 1 <= max_pages <= 100:
        raise ValueError("page_size or max_pages is outside the supported safety bound")

    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/boards/{quote(board_id, safe='')}/pins"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    items: list[dict[str, object]] = []
    seen_bookmarks: set[str] = set()
    bookmark: str | None = None
    pages = 0
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            while True:
                params: dict[str, object] = {"page_size": page_size}
                if bookmark is not None:
                    params["bookmark"] = bookmark
                response = client.get(endpoint, headers=headers, params=params)
                if response.status_code >= 400:
                    raise PinterestReadError(f"Pinterest board read failed with HTTP {response.status_code}")
                try:
                    body = response.json()
                except ValueError as exc:
                    raise PinterestReadError("Pinterest board read returned invalid JSON") from exc
                if not isinstance(body, dict) or not isinstance(body.get("items"), list):
                    raise PinterestReadError("Pinterest board response has an invalid items collection")
                pages += 1
                for item in body["items"]:
                    if isinstance(item, dict):
                        items.append(item)
                next_bookmark = body.get("bookmark")
                if next_bookmark in (None, ""):
                    return {"items": items, "pages_read": pages, "pagination_complete": True}
                if not isinstance(next_bookmark, str) or next_bookmark in seen_bookmarks:
                    raise PinterestReadError("Pinterest board pagination bookmark is invalid or repeated")
                if pages >= max_pages:
                    raise PinterestReadError("Pinterest board pagination safety limit reached; verification incomplete")
                seen_bookmarks.add(next_bookmark)
                bookmark = next_bookmark
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest board read failed due to a transport error") from exc


def get_pin_read_only(*, pin_id: str, access_token: str) -> dict[str, object]:
    """Fetch one Pin's details from Pinterest; performs no write operation."""
    if not pin_id or not pin_id.strip():
        raise ValueError("pin_id is required")
    if not access_token or not access_token.strip():
        raise ValueError("access_token is required")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins/{quote(pin_id, safe='')}"
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.get(endpoint, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        if response.status_code >= 400:
            raise PinterestReadError(f"Pinterest Pin detail read failed with HTTP {response.status_code}")
        body = response.json()
        if not isinstance(body, dict):
            raise PinterestReadError("Pinterest Pin detail response is invalid")
        return body
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest Pin detail read failed due to a transport error") from exc
    except ValueError as exc:
        raise PinterestReadError("Pinterest Pin detail returned invalid JSON") from exc


class PinterestProductTagError(RuntimeError):
    """Sanitized product-tag API error with write-outcome certainty."""
    def __init__(self, message: str, *, http_status: int | None = None, outcome_uncertain: bool = False) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.outcome_uncertain = outcome_uncertain


def list_product_tags_read_only(*, pin_id: str, access_token: str) -> list[str]:
    """Read product Pin IDs currently tagged on a hero Pin."""
    if not pin_id or not pin_id.strip() or not access_token or not access_token.strip():
        raise ValueError("pin_id and access_token are required")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins/{quote(pin_id, safe='')}/product_tags"
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.get(endpoint, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        if response.status_code >= 400:
            raise PinterestReadError(f"Pinterest product-tag read failed with HTTP {response.status_code}")
        body = response.json()
        tags = body.get("product_tags") if isinstance(body, dict) else None
        if not isinstance(tags, list):
            raise PinterestReadError("Pinterest product-tag response is invalid")
        result: list[str] = []
        for tag in tags:
            product_pin_id = tag.get("pin_id") if isinstance(tag, dict) else None
            if not isinstance(product_pin_id, str) or not product_pin_id:
                raise PinterestReadError("Pinterest returned an invalid product-tag entry")
            result.append(product_pin_id)
        return result
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest product-tag read failed due to a transport error") from exc
    except ValueError as exc:
        if isinstance(exc, PinterestReadError):
            raise
        raise PinterestReadError("Pinterest product-tag response returned invalid JSON") from exc


def add_product_tags_to_pin(*, pin_id: str, product_pin_ids: list[str], access_token: str) -> dict[str, object]:
    """Attach existing eligible product Pins to a hero Pin using Pinterest API v5."""
    if not pin_id or not pin_id.strip() or not access_token or not access_token.strip():
        raise ValueError("pin_id and access_token are required")
    if not 1 <= len(product_pin_ids) <= 24:
        raise ValueError("between 1 and 24 product Pin IDs are required")
    if len(set(product_pin_ids)) != len(product_pin_ids) or any(not isinstance(item, str) or not item.strip() for item in product_pin_ids):
        raise ValueError("product Pin IDs must be nonblank and unique")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins/{quote(pin_id, safe='')}/product_tags"
    payload = {"product_tags": [{"pin_id": item} for item in product_pin_ids]}
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.post(endpoint, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "Accept": "application/json"}, json=payload)
    except httpx.RequestError as exc:
        raise PinterestProductTagError("Pinterest product-tag write outcome is uncertain; read the tags before retrying.", outcome_uncertain=True) from exc
    if not response.is_success:
        uncertain = response.status_code >= 500
        raise PinterestProductTagError(
            f"Pinterest rejected product tagging with HTTP {response.status_code}.",
            http_status=response.status_code, outcome_uncertain=uncertain,
        )
    try:
        body = response.json() if response.content else {}
    except ValueError as exc:
        raise PinterestProductTagError("Pinterest accepted the request but returned an unreadable response; verify tags before retrying.", http_status=response.status_code, outcome_uncertain=True) from exc
    if not isinstance(body, dict):
        raise PinterestProductTagError("Pinterest product-tag response is invalid; verify tags before retrying.", http_status=response.status_code, outcome_uncertain=True)
    return body
