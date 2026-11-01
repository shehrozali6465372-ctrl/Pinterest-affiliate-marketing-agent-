# Test helper audit — end-to-end workflow persistence/recovery

Source: `tests/test_workflow_persistence_recovery.py`, SHA `a3a8419b9cb077b1f7a9d0a7d13c0808096d129f`.

- `_payload()` builds a valid synthetic product workflow request.
- `_headers(key)` builds the test API/idempotency headers.
- `_setup_generation(monkeypatch, workflow)` stubs image/content generation so tests isolate persistence and Pinterest-write ordering.
- Nested `pinterest_request(method, path, token, body)` variants capture whether and when a Pinterest write would be attempted; they return a fake Pin response or simulate an ambiguous network outcome.
- `SimulatedNotNullViolation` is a test exception class used to model a database constraint failure.
- `fail_persistence(**kwargs)`, `fail_lookup(_key)` and `fail_attempt(**kwargs)` inject failures at product persistence, idempotency lookup and publication-attempt reservation stages.

Five TEST-WORKFLOW-PERSIST records cover DB failure before Pinterest write, ambiguous write => unknown state and retry blocking, sanitized constraint failure diagnostics, idempotency lookup failure classification, and publication-attempt creation failure before Pinterest write. The module uses fakes/stubs; it does not prove real transaction durability or live Pinterest write behavior.