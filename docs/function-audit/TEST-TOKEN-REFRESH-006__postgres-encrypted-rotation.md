# test_refresh_endpoint_persists_rotated_tokens_encrypted_on_disposable_postgres

- **Unique ID:** TEST-TOKEN-REFRESH-006
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:242-337`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Integration-style test gated by disposable PostgreSQL configuration; uses real PostgreSQL persistence path with a mocked Pinterest OAuth response, then verifies rotated credential storage is encrypted.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
