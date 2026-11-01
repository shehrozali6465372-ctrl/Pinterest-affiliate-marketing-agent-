TEST-API-036 — `test_pinterest_read_only_diagnostic_handles_missing_credential`

Source: `tests/test_api.py`, lines 878–895.

Credential lookup raises `LookupError`; the route responds HTTP 200 with `ok=false` and `error=credential_not_connected`. This records an application-level diagnostic failure in a successful HTTP response; no provider request is made.