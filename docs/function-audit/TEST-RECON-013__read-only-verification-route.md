# test_read_only_pinterest_verification_route_paginates_and_never_mutates

- **Unique ID:** TEST-RECON-013
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:240-266`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks DB and Pinterest read-only helpers; asserts complete pagination, stored Pin match, board match, read_only flag and absence of access token from response.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
