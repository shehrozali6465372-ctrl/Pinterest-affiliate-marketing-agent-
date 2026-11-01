# test_stateful_unknown_state_still_blocks_retry_without_reconciliation

- **Unique ID:** TEST-RECON-012
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:227-238`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts unknown publication state blocks retry and no UPDATE or INSERT statement is issued by the fake harness.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
