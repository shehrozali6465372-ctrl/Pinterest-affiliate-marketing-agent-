# test_http_failure_redacts_secret_reflected_in_provider_metadata

- **Unique ID:** TEST-DEEPSEEK-HTTP-002
- **Definition type:** test function
- **Source:** `tests/test_deepseek_http_diagnostics.py:77-117`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Places the configured secret in response content-type, request ID and provider error metadata; asserts logs and raised exception redact it.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
