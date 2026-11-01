# get_publication — source-level review

- ID: `FN-APP-DATABASE-PY-014`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Parameterized SELECT by publication ID for the fields required by operator status/verification/reconciliation (publication/product/content/board/account/Pin/status metadata). Returns dict row or None. It does not contact Pinterest or mutate publication state.

## Callers and tests
Used by publication status and read-only verification routes. Test coverage is through publication reconciliation route tests with mocked/stateful DB. No DB query was made.
