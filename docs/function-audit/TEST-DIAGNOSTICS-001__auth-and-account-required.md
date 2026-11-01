# test_pinterest_diagnostic_requires_account_id_and_auth

- **Unique ID:** TEST-DIAGNOSTICS-001
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:14-22`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Checks the diagnostic route returns 401 without API key and 422 when authenticated but account_id is missing.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
