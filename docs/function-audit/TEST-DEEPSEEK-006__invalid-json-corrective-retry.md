# test_invalid_json_retry_uses_corrective_prompt_and_recovers

- **Unique ID:** TEST-DEEPSEEK-006
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:163-194`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Returns malformed model JSON then valid JSON; asserts second prompt contains a corrective retry instruction and the generated content succeeds.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
