# begin_publish_attempt

- **Unique ID:** `FN-APP-DATABASE-PY-012`
- **Source:** `app/database.py:237-280`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This record isolates one definition. Review the source line by line, its direct callers, callees, tests and side effects before marking its behavior verified.

## Source excerpt

```python
def begin_publish_attempt(
    *, product_id: int, content_version_id: int, board_id: str, account_id: str | None = None
) -> dict:
    """Reserve one publish attempt per version/board, and retain its owning account."""
    with connection() as conn:
        lock_key = f"{content_version_id}:{board_id}"
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))
        row = conn.execute(
            """
            SELECT * FROM pin_publications
            WHERE content_version_id = %s AND board_id = %s
            FOR UPDATE
            """,
            (content_version_id, board_id),
        ).fetchone()
        if row:
            state = row["status"]
            if state in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, **dict(row)}
            row = conn.execute(
                """
                UPDATE pin_publications
                SET status = 'pending', attempt_count = attempt_count + 1,
                    account_id = COALESCE(account_id, %s),
                    http_status = NULL, error_code = NULL, response_metadata = NULL,
                    last_attempt_at = now(), updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (account_id, row["id"]),
            ).fetchone()
            return {"blocked": False, **dict(row)}
        row = conn.execute(
            """
            INSERT INTO pin_publications
                (product_id, content_version_id, board_id, account_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING *
            """,
            (product_id, content_version_id, board_id, account_id),
        ).fetchone()
        return {"blocked": False, **dict(row)}


```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
