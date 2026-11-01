# test_truncated_json_reports_token_limit_without_logging_content

- **Unique ID:** TEST-DEEPSEEK-002
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:88-98`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Supplies truncated model JSON with finish_reason=length, expects a token-limit ContentGenerationError and verifies raw model content is not logged.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
