# _require_api_key — source-level review

- ID: `FN-APP-LEARNING-PY-001`; source `app/learning.py:23-27`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Requires APP_API_KEY to be configured and X-API-Key header to be present and constant-time equal. Missing configuration/header or mismatch raises HTTP 401. Unlike main.require_api_key, this dependency fails closed when secret is absent.

## Callers and tests
Applied to Learning Loop router. `tests/test_learning.py` focuses metric and snapshot behavior; diagnostics/auth tests cover similar fail-closed route behavior. Endpoint writes analytics snapshots, so API key protection is essential. No endpoint call or DB write occurred.
