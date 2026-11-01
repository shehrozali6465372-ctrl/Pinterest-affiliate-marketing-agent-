# test_stateful_reconciliation_records_audit_metadata_and_rejects_second_transition

- **Unique ID:** TEST-RECON-011
- **Definition type:** test function
- **Source:** `tests/test_publish_reconciliation.py:208-225`
- **Production target:** `app.main` publication status/reconciliation/verification routes and `app.database.reconcile_unknown_publication` / `begin_publish_attempt`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts reconciliation SQL adds operator_board_verification metadata and rejects a second transition after the first succeeds.

## Evidence boundary
Route/database interactions are monkeypatched or run through SQL-shape/state harnesses. These tests do not prove real PostgreSQL row-lock behavior or live Pinterest board completeness. The route verification test specifically stubs the read-only helpers.
