# require_configured_api_key — source-level review

- ID: `FN-APP-MAIN-PY-003`; source `app/main.py:54-60`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
FastAPI dependency reads APP_API_KEY. Missing/falsy configuration returns HTTP 503; missing header or failed hmac.compare_digest returns HTTP 401; valid key returns None. This is fail-closed unlike require_api_key, which allows requests when the key is unset.

## Callers and tests
Used on publish and operator state-changing/reconciliation routes. `tests/test_api.py::test_publish_routes_fail_closed_without_configured_api_key` verifies publish endpoints return 503 when secret is absent. Preserve this dependency for every publish/credential/operator mutation route.
