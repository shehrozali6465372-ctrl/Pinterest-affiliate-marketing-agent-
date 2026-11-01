# database_diagnostic

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-002`
- **Source:** `app/diagnostics.py:24-49`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Runs a database connectivity/read-only diagnostic. Verify that it performs only safe queries, uses bounded timeouts, closes acquired connections and never modifies production rows.

## Exact isolated source

```python
    try:
        from app.database import connection

        with connection() as conn:
            row = conn.execute("SELECT 1 AS connection_test, current_database() AS database_name").fetchone()
        if not row or row.get("connection_test") != 1:
            raise RuntimeError("Database probe returned an unexpected result.")
        return {
            "ok": True,
            "database": "connected",
            "query": "read_only_select_1",
            "database_name": row["database_name"],
            "side_effects": {"data_modified": False, "pinterest_called": False, "ai_generation_called": False},
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection check failed. Verify DATABASE_URL and Neon availability.",
        ) from None


@router.get("/pinterest", dependencies=[Depends(_require_api_key)])
def pinterest_read_only_diagnostic(
    account_id: str = Query(..., min_length=1, max_length=200),
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: source fetched from current main.
- `VERIFIED — DEFINITION ISOLATION`: one definition only.
- `UNVERIFIED — LOGIC`: full call graph, test coverage and failure handling remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic or database operation executed.

## Required checks

Inspect callers, provider/SQL contracts, test cases, timeouts, exception paths, secret redaction, read/write guarantees and cleanup behavior. No live diagnostics are triggered here.
