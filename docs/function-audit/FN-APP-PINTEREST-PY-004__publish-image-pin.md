# publish_image_pin — source-level review

- ID: `FN-APP-PINTEREST-PY-004`; source `app/pinterest.py:34-59`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/publish verification: NOT RUN. Effect: REAL Pinterest Pin creation.

## Control flow
Requires configured legacy static Pinterest access token and nonblank board ID. Builds POST /pins payload containing board_id, title, description, alt_text, media_source from image_media_source, and affiliate URL in `link`. Sends authenticated request with bounded timeout. Transport errors and HTTP 5xx are marked outcome_uncertain; 4xx are definite rejection. Invalid JSON or missing/blank returned Pin ID are uncertain. Success returns Pin ID, HTTP status and limited metadata.

## Callers and tests
Used by legacy versioned publish route. `tests/test_api.py` monkeypatches HTTP client and checks payload/link preservation and 5xx uncertainty. No live Pin was created. Unknown outcomes must be reconciled; never blindly retry.
