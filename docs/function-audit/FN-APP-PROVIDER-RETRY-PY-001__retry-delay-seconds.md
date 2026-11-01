# retry_delay_seconds

- **Unique ID:** `FN-APP-PROVIDER-RETRY-PY-001`
- **Source:** `app/provider_retry.py:9-29`
- **Source blob SHA:** `e654d8e61ac93010ff45fcdda85e5b0856c23850`
- **Snapshot:** `main source snapshot 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Calculates retry delay for provider transient failures. Verify exponential/backoff formula, cap, jitter, Retry-After handling and that retry policy is safe for non-idempotent POST /pins operations.

## Exact isolated source

```python
def retry_delay_seconds(response: object, retry_number: int, *, max_retry_after: float = 8.0) -> float | None:
    """Return a bounded delay, honoring Retry-After; None means defer to caller."""
    headers = getattr(response, "headers", {})
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    provider_delay: float | None = None
    if raw is not None:
        try:
            provider_delay = max(0.0, float(raw))
        except (TypeError, ValueError):
            try:
                retry_at = parsedate_to_datetime(str(raw))
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                provider_delay = max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                provider_delay = None
        if provider_delay is not None and provider_delay > max_retry_after:
            return None
    backoff = min(2 ** max(0, retry_number - 1), 4) + random.uniform(0.0, 0.25)
    return min(max_retry_after, max(backoff, provider_delay or 0.0))
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION RANGE`: single definition isolated.
- `UNVERIFIED — LOGIC CORRECTNESS`: tests and call graph still require verification.
- `UNVERIFIED — LIVE BEHAVIOR`: no external provider call was executed.

## Required checks

Review all call sites, test cases, input boundaries, exception behavior, provider contracts, retry safety and secret redaction.
