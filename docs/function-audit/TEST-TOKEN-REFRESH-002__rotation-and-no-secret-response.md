# test_refresh_endpoint_rotates_and_persists_tokens_without_returning_secrets

- **Unique ID:** TEST-TOKEN-REFRESH-002
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:23-93`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Mocks a provider token response and credential store; asserts rotated tokens are persisted and the HTTP response does not disclose access or refresh token values.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
