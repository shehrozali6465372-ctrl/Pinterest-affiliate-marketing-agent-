# get_publication

- **Unique ID:** `FN-APP-DATABASE-PY-014`
- **Source:** `app/database.py:315-327`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Reads a publication record/status. Verify joins, account scoping, Pin ID consistency, and whether unknown or pending attempts are distinguished.

## Exact isolated source

```python
def get_publication(publication_id: int) -> dict | None:
    """Return only the stored publication fields needed for operator reconciliation."""
    with connection() as conn:
        row = conn.execute(
            """SELECT id, product_id, content_version_id, board_id, account_id,
                      status, attempt_count, pinterest_pin_id, http_status,
                      error_code, response_metadata, created_at, updated_at
               FROM pin_publications WHERE id = %s""",
            (publication_id,),
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
