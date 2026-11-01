TEST-API-035 — `test_pinterest_read_only_diagnostic_checks_account_without_generation`

Source: `tests/test_api.py`, lines 834–877.

The test supplies a stored test credential and fake HTTP client, then calls the protected account diagnostic. It asserts one GET to `/v5/user_account` with a Bearer token, HTTP 200, and false flags for Pin creation, AI generation and image generation. The Pinterest response is mocked.