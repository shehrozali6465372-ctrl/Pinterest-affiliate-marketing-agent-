# retry_delay_seconds — source-level review

- ID: `FN-APP-PROVIDER-RETRY-PY-001`; source `app/provider_retry.py:9-29`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Control flow
1. Reads Retry-After header when available.
2. Parses numeric seconds as non-negative float; if that fails, parses HTTP date, treats naive date as UTC and computes non-negative seconds from current UTC.
3. Malformed Retry-After falls back to exponential backoff.
4. If provider delay exceeds max_retry_after, returns None so caller defers/fails rather than retrying earlier than requested.
5. Computes capped exponential backoff `min(2**max(0,retry_number-1),4)` plus 0–0.25s jitter.
6. Returns min(max_retry_after, max(backoff, provider_delay or 0)).

## Callers and tests
Used by DeepSeek and Cloudflare generation retry logic; callers restrict eligible status/errors and retry count. `test_provider_retry.py` uses synthetic headers. This helper does not perform requests and must not be applied blindly to non-idempotent Pinterest POST /pins. No provider calls occurred.
