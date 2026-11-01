# sanitize

- **Unique ID:** `FN-APP-CONTENT-GENERATION-PY-004`
- **Definition type:** `def`
- **Source:** `app/content_generation.py:39-77`
- **Source blob SHA:** `12d8685abb2883bf4e47526aa99acffc5fd7c36c`
- **Repository snapshot:** `main@336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic overview

Read the complete body below in source order and trace inputs, outputs, validation, dependencies, branches, loops, returns, raised exceptions, persistence and external side effects. This remains unverified until direct callers, callees, tests and runtime behavior are corroborated.

## Inputs, outputs and failure paths

The exact signature, annotations, defaults, validators, return statements, and raises are shown in the source below. Caller-side assumptions and undocumented provider behavior are not treated as facts.

## Exact isolated source

```python
    def sanitize(value: object, limit: int) -> str:
        text = str(value)
        # Sanitize before character filtering: secrets can consist entirely of
        # otherwise-allowed characters and may be reflected by proxies/providers.
        if configured_secret:
            text = text.replace(configured_secret, "[REDACTED]")
        return re.sub(r"[^A-Za-z0-9_.:-]", "_", text)[:limit] or "unknown"

    provider_code = "unknown"
    try:
        error_body = response.json()
        error_obj = error_body.get("error", {}) if isinstance(error_body, dict) else {}
        if isinstance(error_obj, dict):
            candidate = error_obj.get("type") or error_obj.get("code")
            if isinstance(candidate, (str, int)):
                provider_code = sanitize(candidate, 80)
    except (ValueError, TypeError):
        pass
    headers = getattr(response, "headers", {})
    if hasattr(headers, "get"):
        raw_content_type = str(headers.get("content-type", "unknown"))
        if configured_secret:
            raw_content_type = raw_content_type.replace(configured_secret, "[REDACTED]")
        content_type = re.sub(r"[^A-Za-z0-9_./:-]", "_", raw_content_type)[:100] or "unknown"
    else:
        content_type = "unknown"
    raw_request_id = headers.get("x-request-id") or headers.get("request-id") if hasattr(headers, "get") else None
    request_id = sanitize(raw_request_id, 80) if raw_request_id else "unknown"
    response_bytes = len(getattr(response, "content", b"") or b"")
    return {
        "status": int(response.status_code),
        "provider_code": provider_code,
        "content_type": content_type,
        "response_bytes": response_bytes,
        "request_id": request_id,
        "duration_ms": max(0, int(elapsed_ms)),
    }
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed against the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: adjacent/nested definitions are separated by indentation boundary.
- `UNVERIFIED — LOGIC CORRECTNESS`: not yet proven.
- `UNVERIFIED — TEST COVERAGE`: tests and assertions still require mapping/review.
- `UNVERIFIED — LIVE BEHAVIOR`: no runtime or provider claim is made.

## Required next checks

1. Trace direct callers and relevant dependencies.
2. Explain every statement, branch, loop, return and exception path.
3. Inspect tests and map assertions to behavior, including failure and boundary cases.
4. Review concurrency, retries, database transactions and security invariants where relevant.
5. Check the actual external API contract and side effects.
6. No production writes, credential changes, deployments or Pinterest publishing during this audit.
