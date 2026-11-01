# connection — source-level review

- ID: `FN-APP-DATABASE-PY-003`; source `app/database.py:43-48`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
A context manager enters `get_pool().connection()`, yields the leased psycopg connection to the caller, then relies on the pool's context manager to return/release it on normal exit or exception. Transaction commit/rollback behavior is delegated to psycopg_pool's connection context; this wrapper does not issue explicit BEGIN/COMMIT/ROLLBACK and does not catch exceptions.

## Callers and tests
Used by database helpers and credential-vault SQL operations. Unit tests mock pool/connection objects and test lease lifecycle; they do not establish Neon transaction semantics.

## Risks
Nested calls acquire separate leases unless callers pass/reuse a connection explicitly. A thrown exception should propagate through the context manager and trigger psycopg's transaction cleanup. No DB connection was opened in this audit.
