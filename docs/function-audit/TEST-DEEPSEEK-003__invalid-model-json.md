# test_invalid_model_json_has_a_distinct_sanitized_log

- **Unique ID:** TEST-DEEPSEEK-003
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:100-110`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Supplies non-JSON model message content, expects a distinct invalid-JSON ContentGenerationError and verifies the raw content is not logged.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
