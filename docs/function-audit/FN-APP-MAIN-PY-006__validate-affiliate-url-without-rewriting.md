# validate_affiliate_url_without_rewriting

- **Unique ID:** `FN-APP-MAIN-PY-006`
- **Source:** `app/main.py:79-89`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic field validator for affiliate_url. It validates the supplied destination while preserving the original string, which is important for affiliate tracking parameters. Confirm URL parser behavior, allowed schemes, whitespace handling and host restrictions from this exact code.

## Exact isolated source

```python
    def validate_affiliate_url_without_rewriting(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("affiliate_url must not contain leading or trailing whitespace")
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise ValueError("affiliate_url must be an absolute HTTP(S) URL")
        if parts.username or parts.password:
            raise ValueError("affiliate_url must not contain embedded credentials")
        return value
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob retrieved.
- `VERIFIED — LINE RANGE`: isolated by Python definition boundary.
- `UNVERIFIED — LOGIC`: complete call graph, edge cases and tests not yet proven.
- `UNVERIFIED — LIVE BEHAVIOR`: no live endpoint or Pinterest operation invoked.

## Required checks

Trace all callees and route dependencies; inspect associated tests; verify request validation, authorization, idempotency, DB transaction outcomes, Pinterest response parsing, uncertainty handling and affiliate-link preservation. Any publish-capable call must remain unexecuted in this read-only task.
