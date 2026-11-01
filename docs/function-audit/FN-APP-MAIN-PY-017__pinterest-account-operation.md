# pinterest_account_operation

- **Unique ID:** `FN-APP-MAIN-PY-017`
- **Source:** `app/main.py:378-423`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Account-level Pinterest operation handler. Inspect allowed operation values, endpoint mapping, read/write distinction, authorization and response sanitization. Mark any board/pin write side effects explicitly; do not execute them.

## Exact isolated source

```python
def pinterest_account_operation(
    payload: PinterestOperationInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Execute a bounded Pinterest API operation using an encrypted Neon credential."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")
    from app.credential_vault import get_pinterest_credential, revoke_pinterest_credential
    import httpx
    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from exc
    operation = payload.operation
    data = payload.payload
    base = settings.pinterest_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {credential['access_token']}", "Content-Type": "application/json"}
    allowed = {
        "account": ("GET", "/user_account", None),
        "boards": ("GET", "/boards?page_size=100", None),
        "create_board": ("POST", "/boards", {"name": str(data.get("name") or ""), "description": str(data.get("description") or "")}),
        "create_pin": ("POST", "/pins", {"board_id": str(data.get("board_id") or ""), "title": str(data.get("title") or ""), "description": str(data.get("description") or ""), "alt_text": str(data.get("alt_text") or ""), "media_source": {"source_type": "image_url", "url": str(data.get("image_url") or ""), "is_standard": True}, "link": str(data.get("destination_url") or "")}),
    }
    if operation == "disconnect":
        revoke_pinterest_credential(payload.account_id)
        return {"disconnected": True}
    if operation not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported Pinterest operation.")
    method, path, body = allowed[operation]
    if operation == "create_board" and not body["name"]:
        raise HTTPException(status_code=400, detail="Board name is required.")
    if operation == "create_pin" and not all(body.get(k) for k in ("board_id", "title", "link", "media_source")):
        raise HTTPException(status_code=400, detail="Board, title, image URL, and destination URL are required.")
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.request(method, f"{base}{path}", headers=headers, json=body)
        result = response.json() if response.content else {}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Pinterest API request failed.") from exc
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail="Pinterest API rejected or could not complete the operation.")
    return {"data": result}


@app.post("/products/validate", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact code fetched from recorded blob.
- `VERIFIED — SOURCE RANGE`: requested source line range isolated.
- `UNVERIFIED — LOGIC`: caller graph, tests and edge cases remain.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live API, OAuth or DB operation was executed.

## Required checks

Trace authentication dependencies and every downstream function. Inspect positive/negative tests, exception paths, provider contracts, timeouts, retries, persistence atomicity and redaction. No production token or state changes.
