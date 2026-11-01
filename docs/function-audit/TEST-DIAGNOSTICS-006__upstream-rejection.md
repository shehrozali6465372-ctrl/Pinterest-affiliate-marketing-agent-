# test_pinterest_diagnostic_sanitizes_upstream_rejection

- **Unique ID:** TEST-DIAGNOSTICS-006
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:129-163`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Mocks a Pinterest 401 and asserts the diagnostic maps the upstream status and stage without exposing the stored token.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
