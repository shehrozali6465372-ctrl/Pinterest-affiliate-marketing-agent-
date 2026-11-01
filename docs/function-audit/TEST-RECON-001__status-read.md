# test_publication_status_endpoint_only_reads_database

- **Unique ID:** TEST-RECON-001
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:15-27`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts authenticated publication status GET returns the database record and calls only get_publication with the requested ID.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
