# create_content_version — source-level review

- ID: `FN-APP-DATABASE-PY-008`; source `app/database.py:121-159`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Control flow
Opens a connection, takes a transaction-scoped advisory lock keyed by product ID, queries MAX(version_number) for that product, computes next version as max-or-zero plus one, inserts provider/model/prompt version and generated Pin fields, then returns the inserted row as dict. Parameterized values prevent SQL interpolation of product/content fields.

## Callers and invariants
Called by content-generation route and product+initial-content persistence helper. Unique product/version constraint is a second guard. Lock serializes version allocation for same product if the DB transaction is active for the context duration.

## Risks and tests
No explicit content-field validation is done in this helper; route/schema/provider layer is responsible. Fake cursor tests cannot prove lock behavior under concurrent writers. PostgreSQL integration is required; none was run against production.
