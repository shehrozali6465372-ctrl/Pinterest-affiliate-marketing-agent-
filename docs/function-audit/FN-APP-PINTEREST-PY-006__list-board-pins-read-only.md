# list_board_pins_read_only — source-level review

- ID: `FN-APP-PINTEREST-PY-006`; source `app/pinterest.py:64-116`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Control flow
Validates nonblank board ID/access token and page_size 1–250/max_pages 1–100. Builds URL with URL-quoted board ID; loops GET requests with page_size and bookmark. Requires successful HTTP and JSON object containing items list; appends dict items only. Stops with pagination_complete=true only when bookmark absent/empty. Rejects malformed or repeated bookmarks and raises if max page limit reached before completion. Transport/provider failures become PinterestReadError.

## Callers and tests
Used by publication verification to search for stored Pin ID across the board. `test_pinterest_readonly.py` uses fake pages for pagination, repeated bookmarks and safety limit. No live Pinterest reads were performed. Incomplete pagination must never be interpreted as absence.
