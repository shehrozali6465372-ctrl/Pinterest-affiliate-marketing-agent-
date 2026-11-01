# test_unknown_publication_reconciliation_is_durable_and_blocks_duplicate_publish

- **Unique ID:** TEST-PG-PUBLISH-001
- **Definition type:** test function
- **Source:** `tests/test_postgres_publication_recovery.py:57-121`
- **Production target:** `app.database publication state and app.main reconciliation route`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Uses isolated PostgreSQL fixture to reserve, mark unknown, verify retry is blocked, reconcile to succeeded, read durable state via a fresh connection and verify further retries remain blocked. Pinterest is never called.

## Evidence boundary
This integration suite is gated by TEST_DATABASE_URL and is designed for an isolated disposable PostgreSQL database. It does not call Pinterest; it was not executed as part of this audit.
