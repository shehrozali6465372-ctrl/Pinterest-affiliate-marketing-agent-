# _safe_http_failure_metadata — source-level review

- ID: `FN-APP-CONTENT-GENERATION-PY-003`; source `app/content_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Reads configured LLM secret, parses response JSON only to extract error.type or error.code, sanitizes provider code to bounded safe characters, reads content-type and request-id headers with secret redaction, counts response bytes, clamps elapsed milliseconds to non-negative integer, and returns a fixed metadata dict. Malformed JSON/type becomes provider_code=unknown. It never returns raw response body or request headers.

## Callers and tests
Used by DeepSeek HTTP/JSON/schema error paths for structured logs. `test_deepseek_http_diagnostics.py` uses synthetic responses to check redaction/bounds. It does not validate real provider headers. Do not log raw exception response body elsewhere.
