# nonblank

- **Unique ID:** `FN-APP-WORKFLOW-PY-004`
- **Source:** `app/workflow.py:57-63`
- **Blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Pydantic field validator for required text. It rejects empty/whitespace-only values and returns normalized text; verify whether it strips or preserves meaningful whitespace and how non-string values are handled.

## Exact isolated source

```python
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("affiliate_url")
    @classmethod
```

## Evidence tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: one definition only; nested definitions are separate records.
- `UNVERIFIED — LOGIC CORRECTNESS`: callers, tests and security edge cases still need review.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live calls were made.

## Next verification

Inspect all call sites, related Pydantic schemas and route dependencies; map tests for valid/invalid inputs, missing secrets, HTTP transport failures, non-JSON responses, timeouts, retries, and secret redaction. Do not invoke publishing endpoints.
