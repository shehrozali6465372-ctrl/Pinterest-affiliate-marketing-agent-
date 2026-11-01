# test_product_create_reports_missing_database

- **Unique ID:** TEST-API-010
- **Definition type:** test function
- **Source:** `tests/test_api.py:126-131`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 503
assert "DATABASE_URL is not configured" in response.json()["detail"]
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_product_create_reports_missing_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    response = client.post("/products", json=VALID_PRODUCT)
    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.json()["detail"]


```
