# begin_publish_attempt — source-level review

- ID: `FN-APP-DATABASE-PY-012`; source `app/database.py:237-280`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Control flow
1. Opens transaction-scoped DB connection and derives lock key from content_version_id + board_id.
2. Acquires `pg_advisory_xact_lock(hashtext(...))` to serialize attempts for that version/board pair.
3. Selects matching publication row `FOR UPDATE`.
4. If existing status is succeeded, pending or unknown, returns blocked result without creating another attempt.
5. If existing status is failed, resets it to pending, increments attempt_count and refreshes attempt metadata; existing account_id is preserved with COALESCE.
6. If no row exists, inserts pending publication with product/version/board/account and returns row.

## Callers, tests and risks
Used by versioned publish route and end-to-end workflow. `test_publish_recovery_state_machine.py` uses fake cursor/state; `test_postgres_publication_recovery.py` is intended for disposable PostgreSQL. Real advisory-lock/row-lock concurrency is not proven by fake tests. Unique version/board constraint remains final guard. No DB write occurred in this audit.
