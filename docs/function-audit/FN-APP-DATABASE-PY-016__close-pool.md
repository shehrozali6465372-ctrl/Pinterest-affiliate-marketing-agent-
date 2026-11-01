# close_pool — source-level review

- ID: `FN-APP-DATABASE-PY-016`; source `app/database.py:394-400`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Reads module-global `_pool`; if non-None, calls `_pool.close()` then sets global to None. If pool is absent, returns without action. Close exceptions propagate and prevent assignment to None. The helper returns None.

## Callers and tests
Called by FastAPI lifespan shutdown and migration script finally block. Tests mock close_pool/pool close to assert shutdown lifecycle. No live pool was closed in this audit.

## Risks
No lock coordinates close with concurrent connection acquisition or another close call. If close raises, stale global reference remains. Reinitialization is possible only after successful close resets it. Verify multi-worker shutdown separately; each process has its own pool.
