# test_board_reader_fails_closed_on_repeated_bookmark

- **Unique ID:** TEST-PINTEREST-READONLY-002
- **Definition type:** test function
- **Source:** `tests/test_pinterest_readonly.py:54-62`
- **Production target:** `app.pinterest.list_board_pins_read_only` or `app.pinterest.get_pin_read_only`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Supplies the same bookmark twice and expects PinterestReadError containing “repeated”. This tests loop protection against a repeated cursor; provider behavior is mocked.

## Evidence boundary
The module patches the HTTP client with fake responses. A passing test would establish only the asserted local behavior, not live Pinterest API availability, permissions, pagination semantics or production credentials.
