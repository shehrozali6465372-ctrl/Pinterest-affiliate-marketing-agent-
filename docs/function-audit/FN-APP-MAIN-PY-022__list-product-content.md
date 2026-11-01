# list_product_content — source-level review

- ID: `FN-APP-MAIN-PY-022`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Validates positive product ID; confirms parent product exists; queries list_content_versions; returns product_id and serialized version rows ordered by DB helper. Maps missing product to 404 and DB failures to 503. No provider call or mutation.

## Security and tests
Uses require_api_key and therefore is open when APP_API_KEY is unset. API tests mock product and versions; no DB query occurred.
