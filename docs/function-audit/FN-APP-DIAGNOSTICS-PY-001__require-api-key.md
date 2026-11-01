# _require_api_key — source-level review

- ID: `FN-APP-DIAGNOSTICS-PY-001`; source `app/diagnostics.py:16-21`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Reads optional X-API-Key header and configured APP_API_KEY. If config or header is missing, or constant-time comparison fails, raises HTTP 401. Unlike main.require_api_key, this dependency always fails closed when APP_API_KEY is unset. It returns None on valid key.

## Callers and tests
Applied at router level to database, Pinterest and billable generation diagnostics. `tests/test_diagnostics.py` verifies auth is required and account parameter validation order. No diagnostic endpoint was invoked in this audit.
