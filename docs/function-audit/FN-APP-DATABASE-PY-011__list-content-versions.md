# list_content_versions

- **Unique ID:** `FN-APP-DATABASE-PY-011`
- **Source:** `app/database.py:221-236`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Lists content versions for a product. Verify deterministic ordering, pagination/limits, ownership checks and whether newest version selection is unambiguous.

## Exact isolated source

```python
def list_content_versions(product_id: int) -> list[dict]:
    """List saved content versions for a product in newest-first order."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, product_id, version_number, provider, model_id, prompt_version,
                   pin_idea, title, description, alt_text, created_at
            FROM content_versions
            WHERE product_id = %s
            ORDER BY version_number DESC
            """,
            (product_id,),
        ).fetchall()
        return [dict(row) for row in rows]
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from recorded source blob.
- `VERIFIED — LINE RANGE`: one function body isolated.
- `UNVERIFIED — DATA CORRECTNESS`: transaction, constraints, authorization and tests remain to be checked.
- `UNVERIFIED — PRODUCTION DB`: no production data read or written.

## Required checks

Inspect SQL query, migrations, all callers, test assertions, foreign keys, uniqueness, transaction boundaries, race conditions, ordering and error handling. No production DB operations.
