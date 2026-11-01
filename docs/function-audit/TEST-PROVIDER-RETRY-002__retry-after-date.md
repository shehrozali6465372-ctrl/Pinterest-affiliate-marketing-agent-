# test_retry_after_http_date_is_parsed

- **Unique ID:** TEST-PROVIDER-RETRY-002
- **Definition type:** test function
- **Source:** `tests/test_provider_retry.py:16-19`
- **Production target:** `app.provider_retry.retry_delay_seconds`, `app.media_generation.generate_and_host_pin_image`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Supplies an HTTP-date Retry-After value and asserts a delay in the expected range relative to the test's 1970 date. The assertion relies on current clock and only tests the parsed/past-date clamp plus jitter behavior.

## Evidence boundary
HTTP responses are fake; sleep is patched out for retry cases. These tests do not prove Cloudflare availability, current provider error-code semantics, billed usage or real image output quality.
