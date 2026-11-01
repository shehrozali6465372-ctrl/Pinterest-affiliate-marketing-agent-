# restore_pool

- **Unique ID:** TEST-DB-POOL-001
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:12-23`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Autouse fixture saves the previous global pool, resets it for each test, closes a newly created pool defensively and restores the previous global. It isolates global pool lifecycle state.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
