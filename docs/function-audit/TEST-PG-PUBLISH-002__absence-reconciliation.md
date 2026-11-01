# test_unknown_publication_is_not_retryable_until_explicit_absence_reconciliation

- **Unique ID:** TEST-PG-PUBLISH-002
- **Definition type:** test function
- **Source:** `tests/test_postgres_publication_recovery.py:123-154`
- **Production target:** `app.database publication state and app.main reconciliation route`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
On isolated PostgreSQL, verifies unknown blocks retries; explicit operator-verified absence transitions to failed and allows exactly one subsequent pending attempt.

## Evidence boundary
This integration suite is gated by TEST_DATABASE_URL and is designed for an isolated disposable PostgreSQL database. It does not call Pinterest; it was not executed as part of this audit.
