# _serialize_row

- **Unique ID:** `FN-APP-MAIN-PY-009`
- **Definition type:** `def`
- **Source:** `app/main.py:107-115`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Converts database records into API response-compatible dictionaries. Verify conversion for datetime, UUID, Decimal and null values, and confirm credential ciphertext/token columns are excluded.

## Exact isolated source

```python
def _serialize_row(row: dict) -> dict[str, object]:
    result = dict(row)
    created_at = result.get("created_at")
    if created_at:
        result["created_at"] = created_at.isoformat()
    return result


@app.get("/health")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current source blob.
- `VERIFIED — DEFINITION ISOLATION`: indentation-aware boundaries checked.
- `UNVERIFIED — LOGIC`: caller/test/runtime evidence not yet complete.
- `UNVERIFIED — LIVE BEHAVIOR`: no production execution occurred.

## Required checks

Trace every caller/callee, inspect relevant tests, validate boundary cases and exception behavior, and review security/data side effects. Do not call production services during this audit.
