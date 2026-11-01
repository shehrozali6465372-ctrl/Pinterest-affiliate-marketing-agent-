# test_board_reader_follows_every_bookmark_and_only_uses_get

- **Unique ID:** TEST-PINTEREST-READONLY-001
- **Definition type:** test function
- **Source:** `tests/test_pinterest_readonly.py:38-52`
- **Production target:** `app.pinterest.list_board_pins_read_only` or `app.pinterest.get_pin_read_only`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts two mocked GET pages are fetched, the bookmark is passed on page two, Authorization header is present, and the aggregated result reports pagination_complete=true. This verifies the helper's pagination contract against the fake responses only; no live board was read.

## Evidence boundary
The module patches the HTTP client with fake responses. A passing test would establish only the asserted local behavior, not live Pinterest API availability, permissions, pagination semantics or production credentials.
