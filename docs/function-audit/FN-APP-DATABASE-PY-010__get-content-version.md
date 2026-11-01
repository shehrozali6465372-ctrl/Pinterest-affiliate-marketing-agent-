# get_content_version — source-level review

- ID: `FN-APP-DATABASE-PY-010`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Parameterized SELECT for content version constrained by both product_id and content_version_id; returns dict row or None. The composite filter prevents accidentally loading a version belonging to another product.

## Callers and tests
Used by versioned publish route. Route maps missing product/version to 404. Tests use mocked database helper; no DB query was executed.
