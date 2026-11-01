# test_operational_routes_require_api_key_when_configured

- **Unique ID:** TEST-API-006
- **Definition type:** test function
- **Source:** `tests/test_api.py:87-97`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert client.get("/health").status_code == 200
assert client.get("/readiness").status_code == 401
assert client.post("/products/validate", json=VALID_PRODUCT).status_code == 401
assert client.post(
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_operational_routes_require_api_key_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    assert client.get("/health").status_code == 200
    assert client.get("/readiness").status_code == 401
    assert client.post("/products/validate", json=VALID_PRODUCT).status_code == 401
    assert client.post(
        "/products/validate",
        json=VALID_PRODUCT,
        headers={"X-API-Key": "private-test-api-key"},
    ).status_code == 200


```
