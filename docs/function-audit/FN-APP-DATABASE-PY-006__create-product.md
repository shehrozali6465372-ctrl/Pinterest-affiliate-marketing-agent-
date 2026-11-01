# create_product — source-level review

- ID: `FN-APP-DATABASE-PY-006`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Executes parameterized INSERT into products for product_name, product_details, image_url, affiliate_url and optional idempotency_key; returns inserted row. Constraint/unique violations propagate to caller; helper does not translate them or implement retry.

## Callers and tests
Called by POST /products. ProductInput performs URL/length/blank validation. Migration 005 adds nullable idempotency key and partial unique index; legacy rows can omit key. Tests mock persistence and do not exercise Neon. No DB write occurred.
