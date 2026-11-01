TEST-API-037 — `test_deepseek_invalid_json_retries_once_and_returns_real_valid_content`

Source: `tests/test_api.py`, lines 896–949.

The fake DeepSeek client returns truncated JSON first and valid structured content second. Assertions require exactly two POST attempts, the configured model name, parsed title and affiliate disclosure in the description. This verifies retry/parsing behavior against mocked HTTP responses, not the live DeepSeek service.