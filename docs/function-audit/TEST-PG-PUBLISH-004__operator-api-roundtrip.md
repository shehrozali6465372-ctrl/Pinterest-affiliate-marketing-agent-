# test_operator_http_reconciliation_round_trip_on_disposable_postgres

- **Unique ID:** TEST-PG-PUBLISH-004
- **Definition type:** test function
- **Source:** `tests/test_postgres_publication_recovery.py:164-227`
- **Production target:** `app.database publication state and app.main reconciliation route`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Combines FastAPI TestClient with the isolated PostgreSQL fixture; asserts auth gates, unknown state, retry block, operator reconciliation through HTTP, persisted succeeded state and continued duplicate blocking. Pinterest is stubbed/not called.

## Evidence boundary
This integration suite is gated by TEST_DATABASE_URL and is designed for an isolated disposable PostgreSQL database. It does not call Pinterest; it was not executed as part of this audit.
