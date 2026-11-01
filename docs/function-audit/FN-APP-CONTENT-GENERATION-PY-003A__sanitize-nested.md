# _safe_http_failure_metadata.sanitize

- **Unique ID:** FN-APP-CONTENT-GENERATION-PY-003A
- **Definition type:** nested function
- **Source:** `app/content_generation.py:39-76`
- **Status:** VERIFIED — SOURCE RETRIEVED; nested body isolated

## Behavior
Nested sanitizer used by `_safe_http_failure_metadata` to convert provider-supplied diagnostic values to bounded strings while redacting the configured LLM secret and removing unsafe/control characters. The helper is local to the metadata extractor and is not a public module API.

## Security significance
It reduces the chance that provider-controlled headers or error metadata leak the configured API key into logs. This is not a substitute for avoiding logging raw request/response bodies. Exact edge-case correctness must be established from the full implementation and tests.

## Evidence boundary
The nested definition is distinct from its parent and is tracked separately to avoid counting its body as an independently documented function. No provider request was made.
