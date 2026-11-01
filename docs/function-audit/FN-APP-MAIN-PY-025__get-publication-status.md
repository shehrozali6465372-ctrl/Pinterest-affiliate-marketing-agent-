# get_publication_status

- **Unique ID:** `FN-APP-MAIN-PY-025`
- **Source:** `app/main.py:535-552`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Returns persisted publication state for a product/content/account. Verify status mapping and treatment of pending, failed, succeeded and unknown states.

## Exact isolated source

```python
def get_publication_status(publication_id: int) -> dict[str, object]:
    """Inspect a publication record without making any Pinterest requests."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    try:
        row = get_publication(publication_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publication status could not be read") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    for field in ("created_at", "updated_at"):
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    return row


@app.get("/publications/{publication_id}/pinterest-verification", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source.
- `VERIFIED — LINE RANGE`: isolated using neighboring definition boundaries.
- `UNVERIFIED — LOGIC`: callers, tests and edge cases still require review.
- `UNVERIFIED — LIVE BEHAVIOR`: no endpoint/provider action was executed.

## Required checks

Trace direct callees and authorization dependencies; inspect all matching tests; verify database persistence, validation, exception handling, idempotency and no unintended Pinterest side effects.
