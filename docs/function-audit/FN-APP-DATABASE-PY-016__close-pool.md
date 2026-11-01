# close_pool

- **Unique ID:** `FN-APP-DATABASE-PY-016`
- **Source:** `app/database.py:394-400`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Closes the shared PostgreSQL connection pool and resets module state. Verify idempotency, in-flight connection behavior, concurrent shutdown/startup races and whether callers can safely reinitialize the pool.

## Exact isolated source

```python
def close_pool() -> None:
    """Close the connection pool during application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: source fetched from current main.
- `VERIFIED — DEFINITION ISOLATION`: one definition only.
- `UNVERIFIED — LOGIC`: full call graph, test coverage and failure handling remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic or database operation executed.

## Required checks

Inspect callers, provider/SQL contracts, test cases, timeouts, exception paths, secret redaction, read/write guarantees and cleanup behavior. No live diagnostics are triggered here.
