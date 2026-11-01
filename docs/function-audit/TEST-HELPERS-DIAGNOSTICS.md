# Test helper audit — Pinterest diagnostics

Source: `tests/test_diagnostics.py` (175 lines), retrieved from main.

- `_auth(monkeypatch)` sets the app API key to the module's fixed test key; it is shared setup, not an authentication implementation.
- Nested `fake_get_credential(account_id)` records the caller-selected account ID and returns a fake token. It verifies account selection and response redaction in the harness.
- Nested `FakeResponse` instances expose only success/status fields for upstream response simulation.
- Nested `FakeClient.__init__/__enter__/__exit__/get` implements a context-managed HTTP stub and captures URL/Bearer header where relevant; it never opens a network connection.
- Nested `missing(_account_id)`, `invalid_key(_account_id)`, and `missing_database(_account_id)` inject distinct credential/database configuration failures. Their route tests assert sanitized status and detail payloads.

The module's seven tests assert authentication/query validation ordering, caller account ID propagation, no Pin/AI generation flags, missing credential handling, invalid encryption-key and database-configuration classification, sanitized upstream rejection, and application lifespan pool shutdown. These are unit/API harness assertions; they do not verify actual stored credentials, live Pinterest, or Render lifecycle behavior.