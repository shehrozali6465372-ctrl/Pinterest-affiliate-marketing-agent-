# _serialize_row — source-level review

- ID: `FN-APP-MAIN-PY-009`; source `app/main.py:110-115`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Copies input row to a new dict; if created_at is truthy, replaces it with isoformat(); returns dict. It does not recursively serialize nested datetime values or redact secrets. Callers must ensure returned DB rows do not contain token ciphertext or plaintext token columns.

## Callers and tests
Used by product/content/publication route responses. Current selected queries return application row fields, but future SELECT * expansion could expose unintended data. No DB row was fetched from production.
