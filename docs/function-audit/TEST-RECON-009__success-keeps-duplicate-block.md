# test_stateful_reconcile_success_preserves_duplicate_publish_block

- **Unique ID:** TEST-RECON-009
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:167-186`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
With a SQL-shape harness, reconciles unknown to succeeded and asserts a later begin_publish_attempt remains blocked and attempt count is unchanged.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
