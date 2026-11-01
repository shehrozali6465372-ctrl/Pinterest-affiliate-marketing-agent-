# get_product_by_idempotency_key

- **Unique ID:** `FN-APP-DATABASE-PY-005`
- **Source:** `app/database.py:74-86`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Reads the product associated with an idempotency key. Verify uniqueness assumption, account/tenant scoping, query parameterization and race behavior when two requests both observe no row.

## Exact isolated source

```python
def get_product_by_idempotency_key(idempotency_key: str) -> dict | None:
    """Return a previously accepted product for a client retry key."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_name, product_details, image_url, affiliate_url, created_at
            FROM products WHERE idempotency_key = %s
            """,
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: source range contains one definition only.
- `UNVERIFIED — LOGIC CORRECTNESS`: behavior still requires tests, callers and DB contract review.
- `UNVERIFIED — LIVE DATABASE`: no production database operation executed.

## Required checks

Inspect SQL schema and migrations, every caller, test assertions, transaction scope, parameter binding, race conditions, failure recovery and pool lifecycle. No production data mutation is allowed.
