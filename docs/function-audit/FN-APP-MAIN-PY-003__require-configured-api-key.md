# require_configured_api_key

- **Unique ID:** `FN-APP-MAIN-PY-003`
- **Definition:** `def`
- **Source:** `app/main.py:52-61`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Startup/config guard for APP_API_KEY. Verify whether it rejects unset or weak values and whether the guard is invoked on every sensitive route or only selected endpoints.

## Exact isolated source

```python
def require_configured_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Fail closed for publication-changing and operator endpoints if APP_API_KEY is missing."""
    if not settings.app_api_key:
        raise HTTPException(status_code=503, detail="API authentication is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: one definition body isolated.
- `UNVERIFIED — LOGIC`: tests and all call sites remain to be inspected.

## Required checks

Trace route dependencies and model validators, test accepted/rejected values, verify status codes, authentication behavior, data redaction and exception handling.
