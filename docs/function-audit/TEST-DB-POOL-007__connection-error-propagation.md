# test_checkout_connection_context_returns_connection_errors_to_caller

- **Unique ID:** TEST-DB-POOL-007
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery.py:102-118`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts an exception raised entering a pool lease propagates to the caller rather than being swallowed.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
