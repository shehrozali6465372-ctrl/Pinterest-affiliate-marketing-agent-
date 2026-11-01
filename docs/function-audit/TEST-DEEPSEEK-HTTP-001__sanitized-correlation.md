# test_transient_http_failure_logs_sanitized_correlation_metadata

- **Unique ID:** TEST-DEEPSEEK-HTTP-001
- **Definition type:** test function
- **Source:** `tests/test_deepseek_http_diagnostics.py:26-75`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Mocks a 503 then success; asserts retry succeeds and logs status/provider code/attempt/duration/content type/response size/sanitized request ID while excluding API secret and private response body.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
