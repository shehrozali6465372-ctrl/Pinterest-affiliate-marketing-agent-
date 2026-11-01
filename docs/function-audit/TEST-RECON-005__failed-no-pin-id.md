# test_reconcile_failed_cannot_include_pin_id

- **Unique ID:** TEST-RECON-005
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:56-63`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts failed/absence reconciliation cannot include a Pinterest Pin ID.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
