# test_live_diagnostics_requires_api_key_and_never_runs_without_auth

- **Unique ID:** TEST-API-031
- **Definition type:** test function
- **Source:** `tests/test_api.py:719-731`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS REVIEWED; NOT EXECUTED IN THIS AUDIT

## Behavior
Asserts diagnostics POST without API key returns 401.

## Exact source

```python
def test_live_diagnostics_requires_api_key_and_never_runs_without_auth(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(
        diagnostics,
        "run_live_diagnostics",
        lambda payload: {"ok": True, "side_effects": {"pinterest_pin_created": False}},
    )
    response = client.post("/diagnostics/run", json={"account_id": "pinterest:test-account"})
    assert response.status_code == 401


```

## Evidence boundary
The test uses FastAPI TestClient and mocked provider/database dependencies. Its assertions do not establish live Pinterest, DeepSeek, Cloudflare or Neon behavior. In particular, any Pin identifier is supplied by the fake provider response, not created in Pinterest.
