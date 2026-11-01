# database_diagnostic

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-002`
- **Source:** `app/diagnostics.py:22-47`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Uses a PostgreSQL connection and performs a minimal read-only connectivity query, returning structured diagnostic status. Verify connection acquire/release, timeout, exception redaction and that no DDL/DML is executed.

## Exact isolated source

```python
def database_diagnostic() -> dict[str, object]:
    """Verify the application's configured database connection using a read-only query only."""
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — CORRECTED LINE RANGE`: range checked against all definitions in diagnostics.py.
- `UNVERIFIED — LOGIC`: call graph, tests and runtime behavior remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic was run.

## Required checks

Inspect all callers, API and DB dependencies, tests, timeout/exception behavior, read-only side effects and redaction. Do not run this diagnostic against production during the audit.
