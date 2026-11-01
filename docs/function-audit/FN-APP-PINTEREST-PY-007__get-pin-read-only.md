# get_pin_read_only — source-level review

- ID: `FN-APP-PINTEREST-PY-007`; source `app/pinterest.py:117-137`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Behavior
Rejects blank Pin ID/access token; URL-quotes Pin ID into configured `/pins/{id}` endpoint; performs authenticated GET with bounded timeout and Accept: application/json. HTTP errors become PinterestReadError with status; response must parse to dict; transport and JSON errors are sanitized into PinterestReadError. Returns provider JSON for caller-side comparison. No write operation occurs.

## Callers and tests
Used by verify_publication_on_pinterest after listing board Pins. Tests stub HTTP responses; they do not verify current Pinterest API permissions or actual field shape. No live request occurred.
