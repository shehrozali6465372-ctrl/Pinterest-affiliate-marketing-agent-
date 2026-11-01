# evidence_must_be_nonblank

- **Unique ID:** `FN-APP-MAIN-PY-024`
- **Source:** `app/main.py:527-534`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic validator requiring evidence fields for reconciliation. Verify it rejects whitespace-only values and does not permit fabricated/ambiguous evidence.

## Exact isolated source

```python
    def evidence_must_be_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("operator_evidence must not be blank")
        return value


@app.get("/publications/{publication_id}", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source.
- `VERIFIED — LINE RANGE`: isolated using neighboring definition boundaries.
- `UNVERIFIED — LOGIC`: callers, tests and edge cases still require review.
- `UNVERIFIED — LIVE BEHAVIOR`: no endpoint/provider action was executed.

## Required checks

Trace direct callees and authorization dependencies; inspect all matching tests; verify database persistence, validation, exception handling, idempotency and no unintended Pinterest side effects.
