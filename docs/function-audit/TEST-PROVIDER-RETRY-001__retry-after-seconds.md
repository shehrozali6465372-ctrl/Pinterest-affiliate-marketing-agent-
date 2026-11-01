# test_retry_after_seconds_is_honored_and_bounded

- **Unique ID:** TEST-PROVIDER-RETRY-001
- **Definition type:** test function
- **Source:** `tests/test_provider_retry.py:10-14`
- **Production target:** `app.provider_retry.retry_delay_seconds`, `app.media_generation.generate_and_host_pin_image`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts Retry-After seconds is honored when within configured cap and returns None when the provider delay exceeds max_retry_after.

## Evidence boundary
HTTP responses are fake; sleep is patched out for retry cases. These tests do not prove Cloudflare availability, current provider error-code semantics, billed usage or real image output quality.
