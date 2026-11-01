# _safe_http_failure_metadata

- **Unique ID:** `FN-APP-CONTENT-GENERATION-PY-003`
- **Source:** `app/content_generation.py:35-38`
- **Source blob SHA:** `12d8685abb2883bf4e47526aa99acffc5fd7c36c`
- **Snapshot:** `main source snapshot 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Extracts safe metadata from an HTTP failure for logs/diagnostics. Verify it excludes authorization headers, request body, tokens and full provider response while preserving status/code useful for debugging.

## Exact isolated source

```python
def _safe_http_failure_metadata(response: httpx.Response, elapsed_ms: int) -> dict[str, str | int]:
    """Return bounded provider diagnostics with configured credentials redacted."""
    configured_secret = settings.llm_api_key or ""
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION RANGE`: single definition isolated.
- `UNVERIFIED — LOGIC CORRECTNESS`: tests and call graph still require verification.
- `UNVERIFIED — LIVE BEHAVIOR`: no external provider call was executed.

## Required checks

Review all call sites, test cases, input boundaries, exception behavior, provider contracts, retry safety and secret redaction.
