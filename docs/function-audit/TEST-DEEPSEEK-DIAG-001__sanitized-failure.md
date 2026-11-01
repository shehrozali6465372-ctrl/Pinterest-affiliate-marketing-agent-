# test_deepseek_diagnostic_failure_summary_is_sanitized

- **Unique ID:** TEST-DEEPSEEK-DIAG-001
- **Definition type:** test function
- **Source:** `tests/test_deepseek_failure_diagnostics.py:4-50`
- **Production target:** `app.workflow._pinterest_request`, `app.diagnostics.run_live_diagnostics`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks database, Pinterest, Cloudflare and DeepSeek interactions; forces content generation to raise an exception containing sensitive text, then asserts the diagnostic returns a generic failure and excludes the secret text, Pinterest token and configured API key.

## Evidence boundary
Provider HTTP, database access and content generation are mocked. These tests do not prove live Pinterest or DeepSeek behavior, nor do they establish the diagnostics route is bill-free.
