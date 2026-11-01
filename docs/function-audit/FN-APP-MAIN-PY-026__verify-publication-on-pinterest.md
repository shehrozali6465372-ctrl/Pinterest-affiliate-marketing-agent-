# verify_publication_on_pinterest — source-level review

- ID: `FN-APP-MAIN-PY-026`; source `app/main.py:553-598`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Behavior
Loads publication reconciliation data from DB; requires a stored account association and usable credential; reads all Pins for the stored board through `list_board_pins_read_only` (bookmark pagination, repeated-bookmark and max-page checks); requires pagination_complete before treating absence as meaningful; locates the stored Pinterest Pin ID and fetches Pin detail with `get_pin_read_only`. Compares provider Pin/board identity against stored publication data and returns verification evidence. It performs GETs only; no Pin/board writes.

## Callers and evidence
Used by operator verification before reconcile_publication. `tests/test_publish_reconciliation.py` uses fake HTTP/DB state; `test_pinterest_readonly.py` tests pagination edge cases. No live Pinterest read occurred. Incomplete pagination must never be interpreted as Pin absence.
