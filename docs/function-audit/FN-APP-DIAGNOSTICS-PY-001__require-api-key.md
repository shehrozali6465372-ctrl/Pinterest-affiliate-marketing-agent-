# _require_api_key

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-001`
- **Source:** `app/diagnostics.py:16-21`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Authentication dependency used by diagnostic routes. Verify header alias, missing configured key behavior, comparison method and every route that attaches this dependency.

## Exact isolated source

```python
def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


@router.get("/database", dependencies=[Depends(_require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from exact source blob.
- `VERIFIED — LINE RANGE`: isolated against neighboring definitions.
- `UNVERIFIED — LOGIC`: call sites and tests remain to be checked.
