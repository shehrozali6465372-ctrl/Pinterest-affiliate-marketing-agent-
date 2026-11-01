# test_pinterest_diagnostic_uses_caller_account_id_and_never_generates

- **Unique ID:** TEST-DIAGNOSTICS-002
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:24-67`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Mocks stored credential and Pinterest GET; asserts the caller's account ID is used, the bearer token is sent upstream but not returned, and no Pin or AI generation side effect is reported.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
