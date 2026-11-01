# require_api_key

- **Unique ID:** `FN-APP-MAIN-PY-002`
- **Definition:** `def`
- **Source:** `app/main.py:44-51`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

FastAPI dependency that authenticates protected API routes using the configured app key. Verify header name, missing config behavior, constant-time comparison, HTTP status and route coverage.

## Exact isolated source

```python
def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Protect operational endpoints when APP_API_KEY is configured."""
    if not settings.app_api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: one definition body isolated.
- `UNVERIFIED — LOGIC`: tests and all call sites remain to be inspected.

## Required checks

Trace route dependencies and model validators, test accepted/rejected values, verify status codes, authentication behavior, data redaction and exception handling.
