TEST-API-040 — `test_readiness_rejects_present_but_invalid_encryption_key`

Source: `tests/test_api.py`, lines 1095–1104.

A present but invalid Base64 encryption key makes readiness report the key as invalid and the Pinterest account workflow as unconfigured. The test also asserts the supplied key text is not exposed in the response.