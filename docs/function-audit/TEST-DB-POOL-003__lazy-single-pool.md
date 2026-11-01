# test_get_pool_creates_a_single_lazy_pool_with_stale_connection_check

- **Unique ID:** TEST-DB-POOL-003
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:32-57`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Uses FakePool and asserts repeated get_pool calls return one instance configured with expected conninfo, min/max sizes, connection check and open state.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
