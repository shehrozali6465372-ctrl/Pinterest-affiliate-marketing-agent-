# Test helper audit — DeepSeek completion and HTTP diagnostics

Sources retrieved from main: `tests/test_deepseek_completion.py` (252 lines), `tests/test_deepseek_failure_diagnostics.py` (50), and `tests/test_deepseek_http_diagnostics.py` (157).

## Completion helpers
- `FakeResponse.__init__(content, finish_reason, json_error)`: stores a synthetic model response, finish reason and optional envelope parsing exception. `raise_for_status()` is a no-op; `json()` raises the injected error or builds the minimal chat-completions envelope.
- `_install_fake_client(monkeypatch, fake_response, calls)`: installs a fake httpx client; captures timeout, endpoint, headers and request payload; returns the supplied response.
- `_valid_model_json()`: returns schema-shaped sample content with affiliate disclosure.
- Nested `FakeClient` and `SequenceClient` classes model context-manager lifecycle and POST response sequencing. Their methods do not access the network.
- Nested `ErrorResponse` supplies a 503 envelope and raises an httpx HTTPStatusError; nested clients count retries and return the fake response. This checks retry count and log sanitization, not provider recovery.

## Failure-diagnostic helpers
- Nested `FakeConnection.__enter__/__exit__/execute/fetchone` models a successful database probe and asserts the SQL is exactly SELECT 1.
- Nested `FakeHttpClient.__enter__/__exit__/get` returns a successful fake Pinterest account response.
- Nested `fail_generation(**kwargs)` raises a deliberately sensitive-looking message so the test can assert diagnostic output sanitizes it.

## HTTP diagnostic helpers
- `_valid_model_json()` builds a valid structured output fixture.
- Each nested `FakeClient` captures or returns the configured synthetic HTTP response; the three cases test transient 503 then recovery, redaction when secrets are reflected in provider metadata, and redaction after invalid JSON retry exhaustion.

The tests cover structured JSON mode, disabled thinking, image input, token-limit truncation, malformed model JSON vs malformed API envelope, bounded 503 retry, no retry for 429, corrective retry prompts, and safe diagnostic metadata. All provider HTTP responses are synthetic. No live DeepSeek call or live 503 reproduction occurred in this audit.