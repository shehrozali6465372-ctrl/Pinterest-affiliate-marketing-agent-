# test_reconcile_requires_authentication

- **Unique ID:** TEST-RECON-002
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:29-36`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts reconciliation POST returns 401 without the configured X-API-Key.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
