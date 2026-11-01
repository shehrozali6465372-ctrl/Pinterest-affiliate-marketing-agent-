# test_operator_routes_fail_closed_when_api_key_is_not_configured

- **Unique ID:** TEST-RECON-003
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:38-46`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts both status and reconciliation routes return 503 when server-side API key configuration is absent.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
