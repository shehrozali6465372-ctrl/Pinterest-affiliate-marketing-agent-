# test_invalid_api_envelope_is_distinguished_from_model_json

- **Unique ID:** TEST-DEEPSEEK-004
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:112-124`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Makes the provider response envelope JSON parser fail, expects a distinct envelope error, checks response byte metadata and verifies raw invalid response text is not logged.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
