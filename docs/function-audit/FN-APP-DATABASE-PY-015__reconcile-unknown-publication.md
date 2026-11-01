# reconcile_unknown_publication

- **Unique ID:** `FN-APP-DATABASE-PY-015`
- **Source:** `app/database.py:328-393`
- **Source blob SHA:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Transitions an uncertain publication after external evidence is supplied. Verify allowed evidence types, state machine transitions, transaction/locking semantics, whether duplicate Pin IDs are rejected, and whether caller evidence can falsely mark a publication successful.

## Exact isolated source

```python
def reconcile_unknown_publication(
    publication_id: int, *, outcome: str, pinterest_pin_id: str | None = None,
    operator_evidence: str,
) -> dict:
    """Resolve an uncertain publish only after an operator verifies Pinterest state.

    `outcome='succeeded'` requires a Pin ID copied from the verified board listing.
    `outcome='failed'` requires explicit operator confirmation that the Pin is absent.
    This function never calls Pinterest and never makes an uncertain result retryable
    without the caller supplying that verification evidence.
    """
    evidence = operator_evidence.strip()
    if not evidence or len(evidence) > 2000:
        raise ValueError("operator_evidence must be non-empty and at most 2000 characters")
    if outcome == "succeeded":
        if not pinterest_pin_id or not pinterest_pin_id.strip():
            raise ValueError("verified Pinterest Pin ID is required for succeeded reconciliation")
        next_status = "succeeded"
        pin_id = pinterest_pin_id.strip()
    elif outcome == "failed":
        if pinterest_pin_id:
            raise ValueError("Pin ID must be omitted when confirming no Pin exists")
        next_status = "failed"
        pin_id = None
    else:
        raise ValueError("outcome must be 'succeeded' or 'failed'")

    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"publication-reconcile:{publication_id}",))
        row = conn.execute(
            "SELECT * FROM pin_publications WHERE id = %s FOR UPDATE",
            (publication_id,),
        ).fetchone()
        if row is None:
            raise LookupError("publication record was not found")
        if row["status"] != "unknown":
            raise ValueError("only unknown publications may be reconciled")
        if next_status == "succeeded":
            saved = conn.execute(
                """UPDATE pin_publications
                   SET status = 'succeeded', pinterest_pin_id = %s,
                       error_code = NULL,
                       response_metadata = COALESCE(response_metadata, '{}'::jsonb)
                           || jsonb_build_object('reconciliation', jsonb_build_object(
                               'method', 'operator_board_verification', 'evidence', %s::text)),
                       updated_at = now()
                   WHERE id = %s RETURNING *""",
                (pin_id, evidence, publication_id),
            ).fetchone()
        else:
            saved = conn.execute(
                """UPDATE pin_publications
                   SET status = 'failed', pinterest_pin_id = NULL,
                       error_code = 'operator_verified_pin_absent',
                       response_metadata = COALESCE(response_metadata, '{}'::jsonb)
                           || jsonb_build_object('reconciliation', jsonb_build_object(
                               'method', 'operator_board_verification', 'evidence', %s::text)),
                       updated_at = now()
                   WHERE id = %s RETURNING *""",
                (evidence, publication_id),
            ).fetchone()
        if saved is None:
            raise RuntimeError("publication reconciliation did not persist")
        return dict(saved)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: source fetched from current main.
- `VERIFIED — DEFINITION ISOLATION`: one definition only.
- `UNVERIFIED — LOGIC`: full call graph, test coverage and failure handling remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic or database operation executed.

## Required checks

Inspect callers, provider/SQL contracts, test cases, timeouts, exception paths, secret redaction, read/write guarantees and cleanup behavior. No live diagnostics are triggered here.
