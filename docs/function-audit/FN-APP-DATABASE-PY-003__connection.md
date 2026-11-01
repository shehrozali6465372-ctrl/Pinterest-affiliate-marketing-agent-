# connection

- **Unique ID:** `FN-APP-DATABASE-PY-003`
- **Source:** `app/database.py:43-48`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Context manager that obtains a pooled connection for DB operations. Verify acquire/release behavior on success and exception, transaction semantics (autocommit vs explicit transaction), and whether nested calls share one connection.

## Exact isolated source

```python
def connection() -> Iterator[psycopg.Connection]:
    """Yield a pooled PostgreSQL connection."""
    with get_pool().connection() as conn:
        yield conn
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: source range contains one definition only.
- `UNVERIFIED — LOGIC CORRECTNESS`: behavior still requires tests, callers and DB contract review.
- `UNVERIFIED — LIVE DATABASE`: no production database operation executed.

## Required checks

Inspect SQL schema and migrations, every caller, test assertions, transaction scope, parameter binding, race conditions, failure recovery and pool lifecycle. No production data mutation is allowed.
