TEST-API-034 — `test_pinterest_read_only_diagnostic_requires_api_key`

Source: `tests/test_api.py`, lines 828–833.

With an API key configured, an unauthenticated GET to `/diagnostics/pinterest` returns HTTP 401. This checks route authentication in the test client; it does not exercise Pinterest.