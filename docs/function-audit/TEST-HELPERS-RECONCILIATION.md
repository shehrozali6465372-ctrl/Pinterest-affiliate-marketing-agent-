# Test helper audit — publication reconciliation state harness

Source: `tests/test_publish_reconciliation.py`, SHA `3df9cc9ae7e95b7f1e4d63b435fa4ce8d672709a`.

- `auth(monkeypatch)` configures the API key used by protected-route tests.
- Nested `reconcile(publication_id, **kwargs)` captures operator evidence passed to the DB transition stub.
- Nested `Cursor.__init__/execute/fetchone` and `Context.__enter__/__exit__` model SQL cursor and transaction context for rejected-state assertions.
- `StatefulPublicationHarness.__init__/execute/fetchone` simulates publication state, transition evidence, stored Pin ID and duplicate-retry guard. It interprets only the SQL patterns the test expects; it is not PostgreSQL.
- `StatefulConnectionContext.__init__/__enter__/__exit__` exposes the harness through the database context-manager interface.

The 14 separately recorded tests cover status read, auth/fail-closed behavior, success requiring Pin ID, failed state forbidding Pin ID, forwarding operator evidence, rejection of non-unknown DB states, DB Pin-ID validation, durable success blocking duplicate publish, verified absence enabling one retry, audit metadata/single transition, unresolved unknown still blocking retry, and read-only Pinterest verification pagination/auth. Harness-based state tests are not proof of row-lock/concurrency semantics; the separate disposable-Postgres integration module is needed for that.