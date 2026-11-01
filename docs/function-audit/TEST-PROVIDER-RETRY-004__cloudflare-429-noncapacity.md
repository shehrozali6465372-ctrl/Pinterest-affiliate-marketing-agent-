# test_cloudflare_429_non_capacity_error_is_not_retried

- **Unique ID:** TEST-PROVIDER-RETRY-004
- **Definition type:** test function
- **Source:** `tests/test_provider_retry.py:64-81`
- **Production target:** `app.provider_retry.retry_delay_seconds`, `app.media_generation.generate_and_host_pin_image`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Parameterized for provider error codes 3036 and 9999; expects ImageGenerationError HTTP 429 and exactly one POST, demonstrating those codes are not retried.

## Evidence boundary
HTTP responses are fake; sleep is patched out for retry cases. These tests do not prove Cloudflare availability, current provider error-code semantics, billed usage or real image output quality.
