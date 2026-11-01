# test_refresh_preserves_existing_refresh_token_when_provider_omits_rotation

- **Unique ID:** TEST-TOKEN-REFRESH-003
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:95-158`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Mocks a provider response without a replacement refresh token and verifies the existing refresh credential is retained rather than overwritten with null.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
