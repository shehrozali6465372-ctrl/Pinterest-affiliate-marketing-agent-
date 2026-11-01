# create_product_with_content_version — source-level review

- ID: `FN-APP-DATABASE-PY-009`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Uses a single connection/transaction to insert product including idempotency key, then inserts initial content version 1 with provider/model/prompt and generated text, returning both rows. If either statement raises, transaction context should roll back both writes. It does not call Pinterest or provider itself.

## Callers and tests
Called by end-to-end workflow after image/content generation. Unique idempotency index handles concurrent key collision; caller must handle conflict. Workflow persistence tests mock this helper; disposable PostgreSQL test covers atomic behavior intent. No DB transaction was run.
