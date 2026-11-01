# list_board_pins_read_only

- **Unique ID:** `FN-APP-PINTEREST-PY-006`
- **Source:** `app/pinterest.py:64-116`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Read-only Pinterest board Pin listing. Verify token handling, board ID validation, page-size limits, bookmark pagination, response shape and whether it can reliably find a specific Pin beyond the first page.

## Exact isolated source

```python
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from the exact source blob above.
- `VERIFIED — DEFINITION ISOLATION`: one definition and its complete body only.
- `UNVERIFIED — LOGIC CORRECTNESS`: call graph, tests and edge cases remain to be proven.
- `UNVERIFIED — LIVE PINTEREST BEHAVIOR`: no provider call was executed.

## Remaining checks

Trace every caller, review tests, compare request/response with Pinterest API contract, inspect all exceptions and timeout cases, and verify no duplicate Pin can result from retries. Do not call this function during this audit.
