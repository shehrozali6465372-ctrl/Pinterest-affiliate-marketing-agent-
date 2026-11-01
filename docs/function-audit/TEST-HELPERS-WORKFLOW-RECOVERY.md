# Test helper audit — workflow HTTP failure normalization

Source: `tests/test_workflow_recovery.py`, SHA `bc1d397fb5176505141a212b4632025f9552d27d`.

- First nested `FakeClient.__init__/__enter__/__exit__/request` raises a simulated timeout from the Pinterest request path.
- Nested `FakeResponse.json()` supplies a synthetic upstream error body.
- Second nested `FakeClient` implements context management and returns a fake 5xx response from request().

The two TEST-WORKFLOW-RECOVERY records assert timeout and Pinterest 5xx are normalized to gateway errors. Both use fake HTTP behavior; no external request occurs.