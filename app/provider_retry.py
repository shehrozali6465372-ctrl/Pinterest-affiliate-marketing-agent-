"""Small, bounded retry timing helpers for idempotent provider generation calls."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random


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

[executed on device: localhost (bb54f029-ff20-4907-ad1f-8b963b1958c1)]