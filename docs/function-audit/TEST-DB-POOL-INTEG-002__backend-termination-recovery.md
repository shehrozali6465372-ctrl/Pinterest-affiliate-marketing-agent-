# test_pool_replaces_backend_terminated_on_disposable_test_branch

- **Unique ID:** TEST-DB-POOL-INTEG-002
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery_integration.py:99-158`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Opt-in integration test requires PB10_TEST_DATABASE_URL to pass a strict URI allowlist, clears libpq overrides, terminates a backend on that dedicated DB, then verifies the pool obtains a different backend and SELECT 1 succeeds.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
