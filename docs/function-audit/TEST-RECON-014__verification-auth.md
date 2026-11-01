# test_read_only_pinterest_verification_route_requires_auth

- **Unique ID:** TEST-RECON-014
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:268-272`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts the read-only publication verification route returns 401 without API key.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
