# test_disposable_url_guard_rejects_routing_tls_and_fallback_bypasses

- **Unique ID:** TEST-DB-POOL-INTEG-001
- **Definition type:** test function/fixture
- **Source:** `tests/test_database_pool_recovery_integration.py:59-97`
- **Production target:** `app.database.get_pool`, `connection`, `close_pool`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Checks that URI parser rejects production/alternate hosts, host/db overrides, ports, insecure TLS, missing/duplicate TLS params and accepts only the exact disposable Neon host/database with required TLS/channel binding.

## Evidence boundary
Unit tests use fake pool objects. The opt-in integration test terminates a PostgreSQL backend and is safe only when the strict dedicated disposable URI guard passes; it was not executed in this audit. Do not point it at production.
