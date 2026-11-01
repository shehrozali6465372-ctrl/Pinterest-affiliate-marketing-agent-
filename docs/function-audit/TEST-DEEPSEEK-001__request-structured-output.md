# test_deepseek_request_disables_thinking_for_structured_output

- **Unique ID:** TEST-DEEPSEEK-001
- **Definition type:** test function
- **Source:** `tests/test_deepseek_completion.py:70-86`
- **Production target:** `app.content_generation.generate_pin_content`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts DeepSeek request uses JSON-object response format, disables thinking, sets token cap and non-streaming mode, and sends image_url content.

## Evidence boundary
All DeepSeek responses and HTTP clients are faked. Sleep is patched for the retry test. These assertions do not prove current DeepSeek model availability, provider billing, response compatibility or live service recovery.
