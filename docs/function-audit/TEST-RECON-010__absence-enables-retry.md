# test_stateful_reconcile_verified_absence_enables_one_retry

- **Unique ID:** TEST-RECON-010
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:188-206`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
With a SQL-shape harness, records verified absence as failed and asserts the next attempt is allowed and increments attempt_count.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
