# test_pinterest_diagnostic_distinguishes_invalid_encryption_key

- **Unique ID:** TEST-DIAGNOSTICS-004
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:86-106`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Mocks TokenEncryptionConfigurationError and asserts sanitized 503 stage/error fields without returning the detailed key configuration message.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
