# test_checkout_connection_context_uses_pool_connection_context

- **Unique ID:** TEST-DB-POOL-006
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:76-100`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts database.connection delegates checkout and context enter/exit to the pool lease in order.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
