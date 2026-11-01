# test_reconcile_success_requires_pin_id

- **Unique ID:** TEST-RECON-004
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:48-54`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts a succeeded reconciliation without Pinterest Pin ID is rejected with 422.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
