# test_cloudflare_capacity_429_retries_once

- **Unique ID:** TEST-PROVIDER-RETRY-005
- **Definition type:** test function
- **Source:** `tests/test_provider_retry.py:83-105`
- **Production target:** `app.provider_retry.retry_delay_seconds`, `app.media_generation.generate_and_host_pin_image`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks capacity error 3040 followed by success and asserts model identifier and exactly two POST attempts.

## Evidence boundary
HTTP responses are fake; sleep is patched out for retry cases. These tests do not prove Cloudflare availability, current provider error-code semantics, billed usage or real image output quality.
