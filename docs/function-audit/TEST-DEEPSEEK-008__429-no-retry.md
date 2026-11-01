# test_deepseek_429_is_not_retried_as_a_balance_or_server_error

- **Unique ID:** TEST-DEEPSEEK-008
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:230-252`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks HTTP 429 and asserts ContentGenerationError plus exactly one provider call, preventing retry classification as a 5xx/balance recovery path.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
