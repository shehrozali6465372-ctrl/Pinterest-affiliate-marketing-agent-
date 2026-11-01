# test_reconcile_passes_operator_evidence_to_guarded_database_transition

- **Unique ID:** TEST-RECON-006
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:65-84`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts route forwards outcome, Pin ID and operator evidence unchanged to the database transition and returns reconciled/published true for a succeeded row.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
