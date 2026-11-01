# test_migrations_are_idempotent_on_postgres

- **Unique ID:** TEST-PG-PUBLISH-003
- **Definition type:** test function
- **Source:** `tests/test_postgres_publication_recovery.py:156-162`
- **Production target:** `app.database publication state and app.main reconciliation route`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Runs migrations a second time in the isolated PostgreSQL fixture and asserts schema_migrations contains at least eight versions.

## Evidence boundary
This integration suite is gated by TEST_DATABASE_URL and is designed for an isolated disposable PostgreSQL database. It does not call Pinterest; it was not executed as part of this audit.
