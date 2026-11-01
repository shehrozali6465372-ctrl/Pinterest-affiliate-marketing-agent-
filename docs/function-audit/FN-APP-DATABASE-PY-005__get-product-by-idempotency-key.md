# get_product_by_idempotency_key — source-level review

- ID: `FN-APP-DATABASE-PY-005`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Uses connection() and a parameterized SELECT on products.idempotency_key. Returns row as dict when found, otherwise None. It is a read-only lookup and does not reserve the key or serialize concurrent callers.

## Callers and tests
Used as preflight by publish_product_end_to_end. A read-before-write check alone is race-prone; unique partial index from migration 005 is the durable uniqueness guard. Workflow tests mock this lookup. No DB query was run.
