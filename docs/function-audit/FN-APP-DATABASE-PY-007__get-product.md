# get_product

- **Unique ID:** `FN-APP-DATABASE-PY-007`
- **Source:** `app/database.py:108-120`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Fetches a product row by identifier. Verify UUID parsing, not-found behavior, selected columns and whether account ownership is enforced by caller or SQL.

## Exact isolated source

```python
def get_product(product_id: int) -> dict | None:
    """Fetch a single persisted product."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_name, product_details, image_url, affiliate_url, created_at
            FROM products WHERE id = %s
            """,
            (product_id,),
        ).fetchone()
        return dict(row) if row else None
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from recorded source blob.
- `VERIFIED — LINE RANGE`: one function body isolated.
- `UNVERIFIED — DATA CORRECTNESS`: transaction, constraints, authorization and tests remain to be checked.
- `UNVERIFIED — PRODUCTION DB`: no production data read or written.

## Required checks

Inspect SQL query, migrations, all callers, test assertions, foreign keys, uniqueness, transaction boundaries, race conditions, ordering and error handling. No production DB operations.
