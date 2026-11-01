# test_publish_routes_fail_closed_without_configured_api_key

- **Unique ID:** TEST-API-019
- **Definition type:** test function
- **Source:** `tests/test_api.py:377-388`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert direct_route.status_code == 503
assert shorthand_route.status_code == 503
assert "authentication is not configured" in direct_route.json()["detail"]
assert "authentication is not configured" in shorthand_route.json()["detail"]
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_publish_routes_fail_closed_without_configured_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)
    payload = {"product_id": 5, "content_version_id": 12}

    direct_route = client.post("/products/5/content/12/publish")
    shorthand_route = client.post("/publish", json=payload)

    assert direct_route.status_code == 503
    assert shorthand_route.status_code == 503
    assert "authentication is not configured" in direct_route.json()["detail"]
    assert "authentication is not configured" in shorthand_route.json()["detail"]


```
