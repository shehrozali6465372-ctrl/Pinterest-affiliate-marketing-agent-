# _pinterest_request

- **Unique ID:** `FN-APP-WORKFLOW-PY-006`
- **Source:** `app/workflow.py:71-86`
- **Blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Pinterest HTTP adapter. It builds a versioned API URL, sends Bearer auth and JSON body using an HTTPX client with explicit timeouts, parses response JSON, maps transport/JSON failures to HTTP 502, maps provider failures to a controlled HTTP status, and returns status plus payload. Verify non-JSON error bodies, timeout semantics, response-size limits, retries and provider API contract.

## Exact isolated source

```python
def _pinterest_request(method: str, path: str, token: str, *, body: dict | None = None) -> tuple[int, dict]:
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.request(
                method, f"{settings.pinterest_api_base_url.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
            )
        payload = response.json() if response.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Pinterest request failed; verify the account before retrying any publish operation.") from exc
    if not response.is_success:
        raise HTTPException(status_code=response.status_code if response.status_code < 500 else 502, detail=f"Pinterest API rejected the operation (HTTP {response.status_code}).")
    return response.status_code, payload
```

## Evidence tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: one definition only; nested definitions are separate records.
- `UNVERIFIED — LOGIC CORRECTNESS`: callers, tests and security edge cases still need review.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live calls were made.

## Next verification

Inspect all call sites, related Pydantic schemas and route dependencies; map tests for valid/invalid inputs, missing secrets, HTTP transport failures, non-JSON responses, timeouts, retries, and secret redaction. Do not invoke publishing endpoints.
