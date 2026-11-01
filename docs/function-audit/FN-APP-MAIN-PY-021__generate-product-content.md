# generate_product_content — source-level review

- ID: `FN-APP-MAIN-PY-021`; source `app/main.py:468-502`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/provider verification: NOT RUN.

## Behavior
Rejects non-positive product IDs with 422; loads product and returns 404 if absent; calls DeepSeek `generate_pin_content` using stored name/details/image URL; persists returned Pin idea/title/description/alt text and provider/model/prompt version through create_content_version; serializes saved row. ContentGenerationError and RuntimeError map to 503; other exceptions map to generic sanitized 503. It does not publish a Pin.

## Callers, tests and risk
Route uses `require_api_key`, which permits requests if APP_API_KEY is unset. `tests/test_api.py` mocks product/DB and generator to test persistence, and tests missing LLM credentials; these do not call live DeepSeek. P1: absent APP_API_KEY permits a billable generation and DB write. No provider call was made.
