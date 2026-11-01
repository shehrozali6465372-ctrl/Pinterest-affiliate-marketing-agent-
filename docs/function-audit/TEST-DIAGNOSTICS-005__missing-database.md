# test_pinterest_diagnostic_distinguishes_missing_database_configuration

- **Unique ID:** TEST-DIAGNOSTICS-005
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:108-127`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Mocks DatabaseConfigurationError and asserts a sanitized 503 database_configuration error without exposing DATABASE_URL detail.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
