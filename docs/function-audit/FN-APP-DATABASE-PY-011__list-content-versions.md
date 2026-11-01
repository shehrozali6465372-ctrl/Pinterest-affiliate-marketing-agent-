# list_content_versions — source-level review

- ID: `FN-APP-DATABASE-PY-011`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Parameterized SELECT for all content versions belonging to product_id, ordered by version_number descending; returns list of dict rows. It is read-only and does not itself confirm parent product exists.

## Callers and tests
Used by content history route after parent product lookup. Tests mock helper and assert version history returned. No DB query was run.
