# finish_publish_attempt

- **Unique ID:** `FN-APP-DATABASE-PY-013`
- **Source:** `app/database.py:281-314`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This record isolates one definition. Review the source line by line, its direct callers, callees, tests and side effects before marking its behavior verified.

## Source excerpt

```python
def finish_publish_attempt(
    publication_id: int,
    *,
    status: str,
    pinterest_pin_id: str | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    response_metadata: dict | None = None,
) -> dict:
    """Persist outcome metadata from the real Pinterest API, never an access token."""
    if status not in {"succeeded", "failed", "unknown"}:
        raise ValueError("unsupported publication status")
    if status == "succeeded" and not pinterest_pin_id:
        raise ValueError("successful publication requires a confirmed Pinterest Pin ID")
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE pin_publications
            SET status = %s, pinterest_pin_id = %s, http_status = %s,
                error_code = %s, response_metadata = %s::jsonb, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (
                status, pinterest_pin_id, http_status, error_code,
                json.dumps(response_metadata or {}), publication_id,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("publish attempt was not found")
        return dict(row)



```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
