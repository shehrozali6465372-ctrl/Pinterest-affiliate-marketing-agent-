# valid_destination

- **Unique ID:** `FN-APP-WORKFLOW-PY-005`
- **Source:** `app/workflow.py:64-70`
- **Blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Pydantic validator for the affiliate destination URL. It checks destination validity without rewriting the supplied URL. Verify accepted schemes/hosts, malformed URL handling, open-redirect implications and whether URL normalization can alter affiliate attribution.

## Exact isolated source

```python
    def valid_destination(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("affiliate_url must be a valid absolute HTTP(S) URL without embedded credentials or surrounding whitespace")
        return value
```

## Evidence tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: one definition only; nested definitions are separate records.
- `UNVERIFIED — LOGIC CORRECTNESS`: callers, tests and security edge cases still need review.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live calls were made.

## Next verification

Inspect all call sites, related Pydantic schemas and route dependencies; map tests for valid/invalid inputs, missing secrets, HTTP transport failures, non-JSON responses, timeouts, retries, and secret redaction. Do not invoke publishing endpoints.
