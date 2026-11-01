# test_refresh_endpoint_requires_service_key

- **Unique ID:** TEST-TOKEN-REFRESH-001
- **Definition type:** test function
- **Source:** `tests/test_token_refresh.py:14-21`
- **Production target:** `app.main.refresh_pinterest_credential`, `app.credential_vault`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION STATUS NOT CLAIMED

## Test behavior
Checks the credential refresh endpoint requires the dedicated service key and rejects an unauthenticated/incorrect request.

## Evidence boundary
Provider OAuth HTTP is mocked in this test module. The PostgreSQL test only exercises a real DB when its dedicated test database variable is configured; otherwise it is skipped. None of these tests proves live Pinterest OAuth or the production Neon instance.
