# create_product

- **Unique ID:** `FN-APP-DATABASE-PY-006`
- **Source:** `app/database.py:87-107`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Inserts a product record with supplied details and affiliate destination. Verify field validation boundary, URL preservation, unique idempotency constraint handling, SQL parameterization and transaction/rollback behavior.

## Exact isolated source

```python
def create_product(
    *,
    product_name: str,
    product_details: str,
    image_url: str,
    affiliate_url: str,
    idempotency_key: str | None = None,
) -> dict:
    """Persist user-supplied product data and return the stored row."""
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO products (product_name, product_details, image_url, affiliate_url, idempotency_key)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, product_name, product_details, image_url, affiliate_url, created_at, idempotency_key
            """,
            (product_name, product_details, image_url, affiliate_url, idempotency_key),
        ).fetchone()
        return dict(row)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: source range contains one definition only.
- `UNVERIFIED — LOGIC CORRECTNESS`: behavior still requires tests, callers and DB contract review.
- `UNVERIFIED — LIVE DATABASE`: no production database operation executed.

## Required checks

Inspect SQL schema and migrations, every caller, test assertions, transaction scope, parameter binding, race conditions, failure recovery and pool lifecycle. No production data mutation is allowed.
