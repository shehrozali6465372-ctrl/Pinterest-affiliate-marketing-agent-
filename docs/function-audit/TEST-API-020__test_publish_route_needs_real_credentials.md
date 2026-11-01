# test_publish_route_needs_real_credentials

- **Unique ID:** TEST-API-020
- **Definition type:** test function
- **Source:** `tests/test_api.py:390-400`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 503
assert "must be configured" in response.json()["detail"]
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_publish_route_needs_real_credentials(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(settings, "pinterest_access_token", None)
    monkeypatch.setattr(settings, "pinterest_board_id", None)
    response = client.post(
        "/products/5/content/12/publish",
        headers={"X-API-Key": "private-test-api-key"},
    )
    assert response.status_code == 503
    assert "must be configured" in response.json()["detail"]


```
