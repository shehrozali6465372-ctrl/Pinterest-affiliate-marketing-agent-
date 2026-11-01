# create_product — source-level review

- ID: `FN-APP-MAIN-PY-019`; source `app/main.py:435-451`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
FastAPI route depends on `require_api_key` (which returns success when APP_API_KEY is absent). It passes validated ProductInput name/details, normalized image URL and original affiliate URL to database.create_product. Successful row is serialized and returned. RuntimeError maps to 503 with message; other persistence failures map to sanitized 503. This route writes a product row; it does not call providers or publish a Pin.

## Callers, tests and risk
Called by Hub/API clients. `tests/test_api.py` tests missing DB and mocked product persistence/preserved affiliate URL. It tests auth when key is configured but does not prove fail-closed behavior when APP_API_KEY is absent. P1: with missing APP_API_KEY this DB-write route is unauthenticated. No DB write occurred in audit.
