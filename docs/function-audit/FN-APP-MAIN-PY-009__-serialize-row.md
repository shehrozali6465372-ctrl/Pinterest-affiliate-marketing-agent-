# _serialize_row

- **Unique ID:** `FN-APP-MAIN-PY-009`
- **Source:** `app/main.py:107-115`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Converts a DB row into a JSON-safe response object. Verify datetime/UUID/Decimal serialization, null handling, sensitive-field exclusion and consistency across endpoints.

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

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: boundaries checked against neighboring definitions.
- `UNVERIFIED — LOGIC`: tests, callers and behavior remain to be verified.
- `UNVERIFIED — LIVE BEHAVIOR`: no API endpoint was called.

## Required checks

Inspect request/response schema, authentication, direct callees, database query, tests, validation boundaries, failure mapping and secret/data exposure.
