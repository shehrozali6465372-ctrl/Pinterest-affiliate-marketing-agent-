# Test helper audit — API route integration harness

Source: `tests/test_api.py`, baseline SHA `<see source inventory>`, lines 1–1104. All 40 top-level test functions have individual TEST-API-001 through TEST-API-040 records. This document covers nested helper definitions and fake classes.

## Nested helpers and fakes

- In the DeepSeek request test, `FakeResponse.raise_for_status/json` return a controlled success envelope; `FakeClient.__init__/__enter__/__exit__/post` captures timeout, endpoint, headers and JSON payload. No provider request occurs.
- In the content persistence test, `save_version(**kwargs)` captures generated content fields passed to the persistence boundary.
- In Pinterest client contract tests, fake response `json()` returns a synthetic Pin ID; fake clients capture POST endpoint, Bearer header and payload. The 5xx variant returns a synthetic server error to assert uncertain outcome.
- `must_not_publish(**kwargs)` is a guard callback that fails if a duplicate successful publication attempts another write.
- In pre-generation verification tests, `reject_token(*args, **kwargs)` injects credential validation failure; `should_not_generate_image(**kwargs)` ensures image generation is not reached.
- `fail_generation(**kwargs)` injects content-generation failure to verify idempotency state is not consumed prematurely.
- The board-failure and successful end-to-end cases define `pinterest_request(method, path, token, body)` callbacks to record call order and synthesize board/Pin responses. They are in-memory harnesses; they do not make Pinterest requests.
- Diagnostic tests use `FakeConnection.__enter__/__exit__/execute` for SELECT 1, `BrokenConnection` to inject DB failure, `FakeResponse` for Pinterest account GET, and `FakeHttpClient.__init__/__enter__/__exit__/get` to capture URL/auth headers.
- DeepSeek invalid-JSON retry uses `FakeResponse.__init__/raise_for_status/json` plus a sequence-aware `FakeClient` to return invalid then valid model output and capture request payloads.
- Board failure same-key retry and missing-Pin-ID tests define local `pinterest_request` callbacks to simulate external outcomes and assert the workflow's response/state transitions.

## Interpretation limits

These fakes test orchestration, payload construction, branch selection and failure classification. They do not establish Pinterest's real API acceptance, DeepSeek/Cloudflare availability, Neon transaction isolation, OAuth token validity, or that a real Pin was published. The test named `test_publish_is_not_faked` means the production route is not implemented as a fake success path; the test itself still uses controlled mocks to assert behavior and does not perform a live publication.
