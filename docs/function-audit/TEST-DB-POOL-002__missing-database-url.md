# test_get_pool_requires_database_url_without_creating_pool

- **Unique ID:** TEST-DB-POOL-002
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:25-30`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts get_pool raises DatabaseConfigurationError when DATABASE_URL is absent and leaves the global pool unset.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
