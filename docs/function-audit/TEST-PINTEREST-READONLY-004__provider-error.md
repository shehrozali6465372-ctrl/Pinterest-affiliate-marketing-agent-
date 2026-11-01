# test_board_reader_rejects_provider_error_without_exposing_body

- **Unique ID:** TEST-PINTEREST-READONLY-004
- **Definition type:** test function
- **Source:** `tests/test_pinterest_readonly.py:71-77`
- **Production target:** `app.pinterest.list_board_pins_read_only` or `app.pinterest.get_pin_read_only`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Returns a fake HTTP 403 with sensitive body text, expects PinterestReadError with HTTP 403 and asserts the body text is not present in the exception string.

## Evidence boundary
The module patches the HTTP client with fake responses. A passing test would establish only the asserted local behavior, not live Pinterest API availability, permissions, pagination semantics or production credentials.
