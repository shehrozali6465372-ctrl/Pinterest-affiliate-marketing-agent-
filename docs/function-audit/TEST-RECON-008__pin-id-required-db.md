# test_reconcile_database_requires_verified_pin_id_for_success

- **Unique ID:** TEST-RECON-008
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:104-109`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts database reconciliation rejects succeeded outcome without a Pin ID.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
