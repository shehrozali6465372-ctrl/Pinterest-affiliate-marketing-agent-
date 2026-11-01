# get_pin_read_only

- **Unique ID:** `FN-APP-PINTEREST-PY-007`
- **Source:** `app/pinterest.py:117-137`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Read-only Pinterest Pin detail lookup. Verify GET endpoint, authentication, error mapping, returned fields and whether the result contains destination link and board ID needed for publication verification.

## Exact isolated source

```python
def get_pin_read_only(*, pin_id: str, access_token: str) -> dict[str, object]:
    """Fetch one Pin's details from Pinterest; performs no write operation."""
    if not pin_id or not pin_id.strip():
        raise ValueError("pin_id is required")
    if not access_token or not access_token.strip():
        raise ValueError("access_token is required")
    endpoint = f"{settings.pinterest_api_base_url.rstrip('/')}/pins/{quote(pin_id, safe='')}"
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = client.get(endpoint, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
        if response.status_code >= 400:
            raise PinterestReadError(f"Pinterest Pin detail read failed with HTTP {response.status_code}")
        body = response.json()
        if not isinstance(body, dict):
            raise PinterestReadError("Pinterest Pin detail response is invalid")
        return body
    except httpx.RequestError as exc:
        raise PinterestReadError("Pinterest Pin detail read failed due to a transport error") from exc
    except ValueError as exc:
        raise PinterestReadError("Pinterest Pin detail returned invalid JSON") from exc
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from the exact source blob above.
- `VERIFIED — DEFINITION ISOLATION`: one definition and its complete body only.
- `UNVERIFIED — LOGIC CORRECTNESS`: call graph, tests and edge cases remain to be proven.
- `UNVERIFIED — LIVE PINTEREST BEHAVIOR`: no provider call was executed.

## Remaining checks

Trace every caller, review tests, compare request/response with Pinterest API contract, inspect all exceptions and timeout cases, and verify no duplicate Pin can result from retries. Do not call this function during this audit.
