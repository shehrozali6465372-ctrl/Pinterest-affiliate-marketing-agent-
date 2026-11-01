# sanitize — source-level review

- ID: `FN-APP-CONTENT-GENERATION-PY-004`; nested helper in `app/content_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Converts arbitrary metadata value to string, redacts exact configured LLM API key before filtering, replaces characters outside the allowed alphanumeric/underscore/dot/colon/hyphen set with underscores, truncates to caller-supplied limit, and returns `unknown` if result is empty. It is nested inside _safe_http_failure_metadata and used for provider code/request ID values.

## Security limitation
Exact-string replacement does not detect transformed, partial, URL-encoded or otherwise derived secrets. It should only process bounded diagnostic metadata, never prompt/token payloads. Tests cover direct secret redaction and output sanitization; no secret was used in this audit.
