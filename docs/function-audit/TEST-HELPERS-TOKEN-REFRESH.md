# Test helper audit — OAuth token refresh

Source: `tests/test_token_refresh.py`, SHA `4ef24501c26c940b134f05dfd1ffc61707970530`.

- Nested `store(payload)` callbacks capture rotated credential payloads passed to the vault stub.
- Nested `FakeResponse.json()` supplies synthetic token endpoint responses.
- Nested `FakeClient.__init__/__enter__/__exit__/post` captures OAuth token URL, client authentication and form data; variants return rotated refresh tokens, omit refresh-token rotation, or track forbidden calls for expired/malformed expiry cases.
- The disposable-Postgres integration test has nested `FakeResponse` and `FakeClient` classes for the provider side while using a real isolated database fixture for encrypted persistence assertions.

Six TEST-TOKEN-REFRESH records cover service-key auth, token rotation and no secrets in API response, preservation of existing refresh token when provider omits rotation, expired refresh token rejection before provider call, malformed expiry fail-closed, and encrypted persistence on disposable PostgreSQL. Most OAuth provider behavior is mocked; only the opt-in PostgreSQL case is designed to prove encryption persistence against a real DB, and it was not executed during this audit.