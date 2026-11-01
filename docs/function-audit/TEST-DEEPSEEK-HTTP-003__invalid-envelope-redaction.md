# test_invalid_json_retry_exhaustion_redacts_secret_from_content_type

- **Unique ID:** TEST-DEEPSEEK-HTTP-003
- **Definition type:** test function
- **Source:** `tests/test_deepseek_http_diagnostics.py:119-157`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Returns invalid JSON twice with secret embedded in content-type; asserts sanitized ContentGenerationError and redacted logs with bounded response metadata.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
