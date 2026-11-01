# Test fixture audit — disposable PostgreSQL publication recovery

Source: `tests/test_postgres_publication_recovery.py`, SHA `c8bff67efbde29f8151a6a9267313e4325e19091`.

- `isolated_postgres(monkeypatch)` (lines 24–55) is a pytest fixture that provisions an isolated PostgreSQL test database and patches application database settings/migration access for the test scope. Its exact guard/setup/teardown is contained in the source fixture; it must be reviewed as a destructive integration harness and never redirected to production.
- Four separately documented integration tests cover durable unknown-publication reconciliation and duplicate-publish blocking, the requirement for explicit verified absence before retry, migration idempotency on PostgreSQL, and operator HTTP reconciliation round-trip.

These tests are designed for real PostgreSQL behavior, unlike fake-cursor unit tests. Their existence is not evidence they were executed in the current audit; runtime execution status must come from the exact CI run and its configured database service.