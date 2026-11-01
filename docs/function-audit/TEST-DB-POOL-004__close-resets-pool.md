# test_close_pool_closes_and_resets_global_pool

- **Unique ID:** TEST-DB-POOL-004
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:59-68`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts close_pool invokes close once and resets the global _pool to None.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
