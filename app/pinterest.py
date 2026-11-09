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


class PinterestReadError(RuntimeError):
    """A sanitized error from a read-only Pinterest verification request."""


def list_boards_read_only(
    *, access_token: str, page_size: int = 100, max_pages: int = 100,
) -> dict[str, object]:
    """Read the complete authenticated account board list using GET only."""
    if not access_token or not access_token.strip():
        raise ValueError("access_token is required")
    if not 1 <= page_size <= 250 or not 1 <= max_pages <= 100:
        raise ValueError("page_size or max_pages is outside the supported safety bound")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/boards"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    bookmark: str | None = None
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            for _ in range(max_pages):
                params: dict[str, object] = {"page_size": page_size}
                if bookmark is not None:
                    params["bookmark"] = bookmark
                response = client.get(endpoint, headers=headers, params=params)
                if response.status_code >= 400:
                    raise PinterestReadError(f"Pinterest board-list read failed with HTTP {response.status_code}")
                try:
                    body = response.json()
                except ValueError as exc:
                    raise PinterestReadError("Pinterest board-list read returned invalid JSON") from exc
                if not isinstance(body, dict) or not isinstance(body.get("items"), list):
                    raise PinterestReadError("Pinterest board-list response has an invalid items collection")
                for item in body["items"]:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), (str, int)) or not str(item["id"]).strip():
                        raise PinterestReadError("Pinterest board-list response contains an invalid board record")
                    items.append(item)
                next_bookmark = body.get("bookmark")
                if next_bookmark in (None, ""):
                    return {"items": items, "pages_read": len(seen) + 1, "pagination_complete": True}
                if not isinstance(next_bookmark, str) or not next_bookmark.strip() or next_bookmark in seen:
                    raise PinterestReadError("Pinterest board-list pagination bookmark is invalid or repeated")
                seen.add(next_bookmark)
                bookmark = next_bookmark
        raise PinterestReadError("Pinterest board-list pagination safety limit reached; verification incomplete")
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest board-list read failed due to a transport error") from exc


def resolve_board_id_read_only(*, board_name: str, access_token: str) -> dict[str, object]:
    """Resolve exactly one existing board by case-insensitive exact name; never create one."""
    if not board_name or not board_name.strip():
        raise ValueError("board_name is required")
    listing = list_boards_read_only(access_token=access_token)
    matches = [
        item for item in listing["items"]
        if isinstance(item.get("name"), str)
        and item["name"].casefold() == board_name.strip().casefold()
    ]
    if not matches:
        raise PinterestReadError("No exact-name Pinterest board was found on the connected account")
    if len(matches) != 1:
        raise PinterestReadError("Multiple exact-name Pinterest boards were found; board identity is ambiguous")
    return {
        "board_id": str(matches[0]["id"]),
        "board_name": matches[0]["name"],
        "pages_read": listing["pages_read"],
        "pagination_complete": listing["pagination_complete"],
    }


def list_board_pins_read_only(
    *, board_id: str, access_token: str, page_size: int = 250, max_pages: int = 100,
) -> dict[str, object]:
    """Read all pages of a board without creating or changing Pinterest objects."""
    if not board_id or not board_id.strip() or not access_token or not access_token.strip():
        raise ValueError("board_id and access_token are required")
    if not 1 <= page_size <= 250 or not 1 <= max_pages <= 100:
        raise ValueError("page_size or max_pages is outside the supported safety bound")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/boards/{quote(board_id, safe='')}/pins"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    bookmark: str | None = None
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            for _ in range(max_pages):
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
                items.extend(item for item in body["items"] if isinstance(item, dict))
                next_bookmark = body.get("bookmark")
                if next_bookmark in (None, ""):
                    return {"items": items, "pages_read": len(seen) + 1, "pagination_complete": True}
                if not isinstance(next_bookmark, str) or next_bookmark in seen:
                    raise PinterestReadError("Pinterest board pagination bookmark is invalid or repeated")
                seen.add(next_bookmark)
                bookmark = next_bookmark
        raise PinterestReadError("Pinterest board pagination safety limit reached; verification incomplete")
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest board read failed due to a transport error") from exc


def get_pin_read_only(*, pin_id: str, access_token: str) -> dict[str, object]:
    """Fetch one Pin's details using GET only."""
    if not pin_id or not pin_id.strip() or not access_token or not access_token.strip():
        raise ValueError("pin_id and access_token are required")
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
