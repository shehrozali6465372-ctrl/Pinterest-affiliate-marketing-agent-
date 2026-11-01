# health

- **Unique ID:** `FN-APP-MAIN-PY-010`
- **Source:** `app/main.py:116-120`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Basic liveness endpoint. Verify it has no dependency on DB/provider readiness and returns stable status without leaking deployment details.

## Exact isolated source

```python
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pinterest-affiliate-model-1"}


@app.get("/readiness", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: boundaries checked against neighboring definitions.
- `UNVERIFIED — LOGIC`: tests, callers and behavior remain to be verified.
- `UNVERIFIED — LIVE BEHAVIOR`: no API endpoint was called.

## Required checks

Inspect request/response schema, authentication, direct callees, database query, tests, validation boundaries, failure mapping and secret/data exposure.
