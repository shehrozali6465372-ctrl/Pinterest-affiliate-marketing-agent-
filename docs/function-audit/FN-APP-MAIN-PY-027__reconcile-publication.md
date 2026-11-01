# reconcile_publication — source-level review

- ID: `FN-APP-MAIN-PY-027`; source `app/main.py:599-626`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Requires configured API key through `require_configured_api_key`; validates request body with PublicationReconciliationInput, including bounded nonblank operator evidence; delegates outcome, optional Pin ID and evidence to database.reconcile_unknown_publication; maps missing publication/invalid state/input/DB errors to appropriate sanitized HTTP errors and serializes result. It does not query Pinterest itself and does not create/delete Pins.

## Trust boundary and tests
Caller must first perform `verify_publication_on_pinterest` and supply truthful evidence. Database helper permits only unknown-to-succeeded (with Pin ID) or unknown-to-failed (without Pin ID). Tests in `test_publish_reconciliation.py` use TestClient and stateful fake SQL harness; real row locks require disposable PostgreSQL. No reconciliation was executed.
