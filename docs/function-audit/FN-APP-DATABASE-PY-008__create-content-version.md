# create_content_version

- **Unique ID:** `FN-APP-DATABASE-PY-008`
- **Source:** `app/database.py:121-159`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Persists a versioned Pin content record associated with a product. Verify version numbering under concurrent writers, immutable history guarantees, foreign-key behavior and whether title/description/alt text are validated before insert.

## Exact isolated source

```python
def create_content_version(
    *,
    product_id: int,
    provider: str,
    model_id: str,
    prompt_version: str,
    pin_idea: str,
    title: str,
    description: str,
    alt_text: str,
) -> dict:
    """Persist generated content as an auditable version for the supplied product."""
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (product_id,))
        version_number = conn.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM content_versions WHERE product_id = %s
            """,
            (product_id,),
        ).fetchone()["next_version"]
        row = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, product_id, version_number, provider, model_id, prompt_version,
                      pin_idea, title, description, alt_text, created_at
            """,
            (
                product_id, version_number, provider, model_id, prompt_version,
                pin_idea, title, description, alt_text,
            ),
        ).fetchone()
        return dict(row)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from recorded source blob.
- `VERIFIED — LINE RANGE`: one function body isolated.
- `UNVERIFIED — DATA CORRECTNESS`: transaction, constraints, authorization and tests remain to be checked.
- `UNVERIFIED — PRODUCTION DB`: no production data read or written.

## Required checks

Inspect SQL query, migrations, all callers, test assertions, foreign keys, uniqueness, transaction boundaries, race conditions, ordering and error handling. No production DB operations.
