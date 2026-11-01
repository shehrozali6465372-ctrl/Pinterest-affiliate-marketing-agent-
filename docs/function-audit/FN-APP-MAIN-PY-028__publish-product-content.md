# publish_product_content — source-level review

- ID: `FN-APP-MAIN-PY-028`; source `app/main.py:627-680`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/publish verification: NOT RUN. Effect: REAL Pinterest POST /pins.

## Control flow
Validates positive product/content IDs; loads product and content version constrained to that product; requires configured static Pinterest access token and board ID for this legacy route; begins durable publication attempt keyed by content version/board; returns prior succeeded result when blocked by existing successful state; converts image URL/data URL to Pinterest media source; calls `publish_image_pin` with title/description/alt text and affiliate URL; persists succeeded Pin ID/metadata or failed/unknown state according to error certainty. Exceptions are mapped to HTTP responses without claiming success unless a Pin ID is confirmed.

## Tests and risk
`tests/test_api.py` mocks database and Pinterest client and checks success/duplicate prevention/uncertain outcomes. This route uses legacy static token config, not stored account credential. It is a real publish endpoint and was not invoked. Never blindly retry an unknown outcome.
