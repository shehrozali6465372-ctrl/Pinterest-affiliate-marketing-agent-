# test_malformed_refresh_token_expiry_fails_closed

- **Unique ID:** TEST-TOKEN-REFRESH-005
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:199-240`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Provides malformed refresh-token expiry data and asserts fail-closed behavior before provider refresh.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
