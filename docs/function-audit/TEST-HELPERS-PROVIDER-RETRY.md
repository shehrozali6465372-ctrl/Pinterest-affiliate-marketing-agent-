# Test helper audit — provider retry and Cloudflare

Source: `tests/test_provider_retry.py`, SHA `e8d65e57ef4924895e400f33536c202156e26c4f`.

- `FakeResponse.__init__(status_code, body, headers, content)` stores response metadata; `json()` returns the supplied body.
- `_configure_cloudflare(monkeypatch)` installs test Cloudflare configuration used by each provider retry case.
- Nested fake clients implement context-manager methods and POST behavior; they return queued HTTP responses and record calls without opening network connections.

Five separate TEST-PROVIDER-RETRY records cover numeric Retry-After bounded delay, HTTP-date Retry-After parsing, Cloudflare 503 retry and recovery, non-capacity 429 no-retry, and capacity-related 429 retry. These tests verify retry policy under controlled responses, not Cloudflare account permissions, actual rate limits, or billable image generation.