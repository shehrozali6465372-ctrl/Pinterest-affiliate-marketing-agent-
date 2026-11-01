# test_pinterest_diagnostic_reports_missing_credential_without_calling_api

- **Unique ID:** TEST-DIAGNOSTICS-003
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:69-84`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Makes credential lookup raise LookupError and asserts a sanitized credential_not_connected result; no Pinterest request client is installed.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
