# test_expired_refresh_token_is_rejected_before_provider_call

- **Unique ID:** TEST-TOKEN-REFRESH-004
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:160-197`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Uses an expired refresh-token expiry and a fake client that must not be called; asserts the refresh is rejected before contacting Pinterest.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
