# reconcile_unknown_publication — source-level review

- ID: `FN-APP-DATABASE-PY-015`; source `app/database.py:328-393`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Control flow
1. Validates outcome is succeeded or failed; success requires Pin ID and failure must not include one.
2. Strips operator evidence and enforces non-empty/bounded length.
3. Acquires transaction-scoped advisory lock for publication ID.
4. Selects publication row FOR UPDATE and requires current status unknown.
5. Updates status, Pin ID, evidence/metadata and timestamp; returns updated row.
6. Does not call Pinterest; correctness depends on operator evidence from the separate read-only verification route.

## Callers and tests
Called by authenticated operator reconciliation endpoint after status/verification workflow. `test_publish_reconciliation.py` exercises route/state harness; `test_postgres_publication_recovery.py` targets real DB state in disposable PostgreSQL. No production DB write or Pinterest read occurred.

## Risks
Evidence is free-form text rather than a typed record of source, verifier, timestamp and pagination completeness. Ensure only a complete Pinterest read can justify marking absent Pin as failed. No automatic retry should follow unknown state.
