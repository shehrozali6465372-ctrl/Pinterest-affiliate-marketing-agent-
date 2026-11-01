# run_migrations — source-level review

- ID: `FN-APP-DATABASE-PY-004`; source `app/database.py:49-73`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Control flow
1. Acquires one pooled connection.
2. Creates `schema_migrations` if absent.
3. Acquires transaction-scoped PostgreSQL advisory lock with fixed key 73219021 to serialize migration runners.
4. Locates repository migrations directory and enumerates numbered `.sql` files in lexical order.
5. Reads recorded versions; skips already-recorded migration names.
6. Executes each remaining SQL file and inserts its version record on the same connection.
7. Returns None after all migrations; SQL/IO errors propagate.

## Risks and evidence
No checksum is stored, so editing an already-applied migration is not detected. Atomicity depends on psycopg transaction context and server SQL behavior; static review cannot prove deployed schema state. `tests/test_postgres_publication_recovery.py` includes disposable-PostgreSQL migration behavior. No migration was executed.
