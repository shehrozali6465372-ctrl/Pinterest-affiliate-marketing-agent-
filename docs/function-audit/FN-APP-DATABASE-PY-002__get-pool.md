# get_pool

- **Unique ID:** `FN-APP-DATABASE-PY-002`
- **Source:** `app/database.py:23-42`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Lazily initializes/reuses the PostgreSQL connection pool using configured DATABASE_URL and pool settings. Verify singleton/thread-safety behavior, connection limits, startup race handling, timeout defaults and recovery after pool closure.

## Exact isolated source

```python
def get_pool() -> ConnectionPool:
    """Create the pool lazily so liveness checks work without a DB connection."""
    global _pool
    if not settings.database_url:
        raise DatabaseConfigurationError("DATABASE_URL is not configured; product persistence is unavailable.")
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=5,
            # Validate idle connections on checkout so Neon/server-side idle
            # disconnects are discarded and replaced instead of handed to a query.
            check=ConnectionPool.check_connection,
            open=True,
        )
    return _pool


@contextmanager
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: source range contains one definition only.
- `UNVERIFIED — LOGIC CORRECTNESS`: behavior still requires tests, callers and DB contract review.
- `UNVERIFIED — LIVE DATABASE`: no production database operation executed.

## Required checks

Inspect SQL schema and migrations, every caller, test assertions, transaction scope, parameter binding, race conditions, failure recovery and pool lifecycle. No production data mutation is allowed.
