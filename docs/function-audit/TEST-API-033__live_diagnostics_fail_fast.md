TEST-API-033 — `test_live_diagnostics_does_not_call_image_generator_if_db_or_pinterest_fails`

Source: `tests/test_api.py`, lines 796–827.

The test makes the database connection fail and credential lookup raise, then asserts diagnostics fail and the image generator is not called. It verifies a fail-fast guard using stubs, not a live database/provider failure.