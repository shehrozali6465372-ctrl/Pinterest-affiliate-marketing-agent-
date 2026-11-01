# test_reconcile_database_rejects_non_unknown_states

- **Unique ID:** TEST-RECON-007
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:86-102`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Uses a fake SQL cursor returning a succeeded publication and asserts database reconciliation rejects transition because only unknown states may be reconciled.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
