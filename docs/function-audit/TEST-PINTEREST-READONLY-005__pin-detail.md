# test_pin_detail_reader_uses_get_and_returns_json

- **Unique ID:** TEST-PINTEREST-READONLY-005
- **Definition type:** test function
- **Source:** `tests/test_pinterest_readonly.py:79-85`
- **Production target:** `app.pinterest.list_board_pins_read_only` or `app.pinterest.get_pin_read_only`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts get_pin_read_only returns the fake Pin JSON and requests the /pins/pin-1 endpoint. It does not assert headers or validate real Pinterest response shape.

## Evidence boundary
The module patches the HTTP client with fake responses. A passing test would establish only the asserted local behavior, not live Pinterest API availability, permissions, pagination semantics or production credentials.
