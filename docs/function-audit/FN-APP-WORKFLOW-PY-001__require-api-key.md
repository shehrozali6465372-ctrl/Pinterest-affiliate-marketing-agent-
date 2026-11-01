# _require_api_key

- **Unique ID:** `FN-APP-WORKFLOW-PY-001`
- **Source:** `app/workflow.py:27-31`
- **Blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

FastAPI dependency guard. It obtains the supplied API-key header and compares it with configured APP_API_KEY; missing configuration or mismatch must reject the request. Security correctness depends on constant-time comparison, header parsing and consistent route dependency attachment; verify those details from the body and tests.

## Exact isolated source

```python
def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")
```

## Evidence tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: one definition only; nested definitions are separate records.
- `UNVERIFIED — LOGIC CORRECTNESS`: callers, tests and security edge cases still need review.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live calls were made.

## Next verification

Inspect all call sites, related Pydantic schemas and route dependencies; map tests for valid/invalid inputs, missing secrets, HTTP transport failures, non-JSON responses, timeouts, retries, and secret redaction. Do not invoke publishing endpoints.
