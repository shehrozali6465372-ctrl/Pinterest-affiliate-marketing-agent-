# test_cloudflare_503_retries_once_then_returns_image

- **Unique ID:** TEST-PROVIDER-RETRY-003
- **Definition type:** test function
- **Source:** `tests/test_provider_retry.py:39-62`
- **Production target:** `app.provider_retry.retry_delay_seconds`, `app.media_generation.generate_and_host_pin_image`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks Cloudflare returning 503 then 200 with Base64 image content. Asserts generated data URL and exactly two POST attempts.

## Evidence boundary
HTTP responses are fake; sleep is patched out for retry cases. These tests do not prove Cloudflare availability, current provider error-code semantics, billed usage or real image output quality.
