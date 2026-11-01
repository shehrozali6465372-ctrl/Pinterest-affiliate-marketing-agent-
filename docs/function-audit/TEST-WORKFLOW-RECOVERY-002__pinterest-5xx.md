# test_workflow_pinterest_5xx_is_normalized_to_gateway_error

- **Unique ID:** TEST-WORKFLOW-RECOVERY-002
- **Definition type:** test function
- **Source:** `tests/test_workflow_recovery.py:33-61`
- **Production target:** `app.workflow._pinterest_request`, `app.diagnostics.run_live_diagnostics`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks a Pinterest 503 response and asserts _pinterest_request raises HTTP 502 with upstream HTTP 503 context.

## Evidence boundary
Provider HTTP, database access and content generation are mocked. These tests do not prove live Pinterest or DeepSeek behavior, nor do they establish the diagnostics route is bill-free.
