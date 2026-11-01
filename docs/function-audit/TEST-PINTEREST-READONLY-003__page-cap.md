# test_board_reader_does_not_claim_complete_when_page_cap_reached

- **Unique ID:** TEST-PINTEREST-READONLY-003
- **Definition type:** test function
- **Source:** `tests/test_pinterest_readonly.py:64-69`
- **Production target:** `app.pinterest.list_board_pins_read_only` or `app.pinterest.get_pin_read_only`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Sets max_pages=1 while the fake response returns another bookmark and expects a safety-limit error. It asserts incomplete pagination is not represented as success.

## Evidence boundary
The module patches the HTTP client with fake responses. A passing test would establish only the asserted local behavior, not live Pinterest API availability, permissions, pagination semantics or production credentials.
