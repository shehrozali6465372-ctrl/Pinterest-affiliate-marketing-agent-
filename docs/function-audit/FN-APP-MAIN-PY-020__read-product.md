# read_product — source-level review

- ID: `FN-APP-MAIN-PY-020`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Rejects non-positive product ID with 422; calls database.get_product; maps DB/config errors to 503; returns 404 when row absent; otherwise serializes created_at and returns product. Read-only DB route.

## Security and tests
Uses require_api_key, which permits access if APP_API_KEY is unset. API tests mock DB and cover not-found. Product data may include user-supplied affiliate/product details; no account-level authorization is visible in this route.
