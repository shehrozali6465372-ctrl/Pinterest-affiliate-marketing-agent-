# run_migrations

- **Unique ID:** `FN-APP-DATABASE-PY-004`
- **Source:** `app/database.py:49-73`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Applies SQL migration files to the configured PostgreSQL database. Verify migration ordering, checksum/version tracking, atomicity, duplicate execution safety, path resolution and whether migration execution is safe during concurrent service startup.

## Exact isolated source

```python
def run_migrations() -> None:
    """Apply each numbered SQL migration once, in lexical order."""
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("SELECT pg_advisory_xact_lock(73219021)")
        for migration in sorted(_MIGRATIONS_DIR.glob("[0-9]*.sql")):
            version = migration.name
            existing = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
            ).fetchone()
            if existing:
                continue
            conn.execute(migration.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: source range contains one definition only.
- `UNVERIFIED — LOGIC CORRECTNESS`: behavior still requires tests, callers and DB contract review.
- `UNVERIFIED — LIVE DATABASE`: no production database operation executed.

## Required checks

Inspect SQL schema and migrations, every caller, test assertions, transaction scope, parameter binding, race conditions, failure recovery and pool lifecycle. No production data mutation is allowed.
