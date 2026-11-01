# get_content_version

- **Unique ID:** `FN-APP-DATABASE-PY-010`
- **Source:** `app/database.py:206-220`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Reads a specific content version. Verify product/content relationship checks, not-found semantics and authorization boundaries.

## Exact isolated source

```python
def get_content_version(product_id: int, content_version_id: int) -> dict | None:
    """Fetch one generated content version belonging to a product."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_id, version_number, provider, model_id, prompt_version,
                   pin_idea, title, description, alt_text, created_at
            FROM content_versions
            WHERE product_id = %s AND id = %s
            """,
            (product_id, content_version_id),
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
