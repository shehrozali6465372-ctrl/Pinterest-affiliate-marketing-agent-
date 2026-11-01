# get_publication_status — source-level review

- ID: `FN-APP-MAIN-PY-025`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Uses fail-closed configured API-key dependency; loads publication row by ID using database.get_publication; returns 404 if missing and serializes stored status/metadata if found. It does not query Pinterest, prove Pin existence or change state.

## Callers and tests
Operator uses it to inspect pending/unknown/succeeded state before verification/reconciliation. Tests exercise route with fake DB. No production record was read.
