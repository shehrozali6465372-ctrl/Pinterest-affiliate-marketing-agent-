# test_workflow_pinterest_timeout_is_reported_as_gateway_error

- **Unique ID:** TEST-WORKFLOW-RECOVERY-001
- **Definition type:** test function
- **Source:** `tests/test_workflow_recovery.py:11-31`
- **Production target:** `app.workflow._pinterest_request`, `app.diagnostics.run_live_diagnostics`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks httpx.Client to raise ReadTimeout from _pinterest_request and asserts HTTP 502 plus instruction to verify the account before retrying. This checks the uncertain-write timeout mapping in the fake client.

## Evidence boundary
Provider HTTP, database access and content generation are mocked. These tests do not prove live Pinterest or DeepSeek behavior, nor do they establish the diagnostics route is bill-free.
