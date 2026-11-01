# publish_image_pin

- **Unique ID:** `FN-APP-PINTEREST-PY-004`
- **Source:** `app/pinterest.py:34-59`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Low-level Pinterest Pin creation helper. It builds POST /pins with board, content, alt text, media and destination URL, then parses the returned Pin ID or raises a controlled error. This is a real side-effecting function; it was not called. Verify timeouts, status mapping, response schema and duplicate/uncertain outcome behavior.

## Exact isolated source

```python
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from the exact source blob above.
- `VERIFIED — DEFINITION ISOLATION`: one definition and its complete body only.
- `UNVERIFIED — LOGIC CORRECTNESS`: call graph, tests and edge cases remain to be proven.
- `UNVERIFIED — LIVE PINTEREST BEHAVIOR`: no provider call was executed.

## Remaining checks

Trace every caller, review tests, compare request/response with Pinterest API contract, inspect all exceptions and timeout cases, and verify no duplicate Pin can result from retries. Do not call this function during this audit.
