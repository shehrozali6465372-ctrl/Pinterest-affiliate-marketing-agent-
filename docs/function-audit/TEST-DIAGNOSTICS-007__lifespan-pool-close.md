# test_app_lifespan_closes_database_pool

- **Unique ID:** TEST-DIAGNOSTICS-007
- **Definition type:** test function
- **Source:** `tests/test_diagnostics.py:165-175`
- **Production target:** `app.diagnostics and FastAPI diagnostics/lifespan routes`
- **Status:** VERIFIED — ASSERTIONS MAPPED; EXECUTION NOT CLAIMED

## Test behavior
Patches close_pool and asserts FastAPI TestClient lifespan shutdown invokes it exactly once.

## Evidence boundary
HTTP/provider/database behavior is mocked. Assertions do not establish live provider behavior or production service availability.
