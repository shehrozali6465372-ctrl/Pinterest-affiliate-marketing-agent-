# test_deepseek_http_503_retries_once_then_logs_provider_code_without_secret

- **Unique ID:** TEST-DEEPSEEK-005
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:126-161`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks HTTP 503 twice, patches sleep, asserts exactly two calls, sanitized provider code in logs, and no private body or API key leakage.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
