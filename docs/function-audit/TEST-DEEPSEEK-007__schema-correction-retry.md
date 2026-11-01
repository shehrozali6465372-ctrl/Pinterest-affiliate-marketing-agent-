# test_schema_invalid_retry_uses_schema_correction_and_recovers

- **Unique ID:** TEST-DEEPSEEK-007
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:196-228`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Returns schema-invalid content then valid JSON; asserts second prompt contains schema correction and generation succeeds.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
