# test_publish_route_does_not_duplicate_successful_pin

- **Unique ID:** TEST-API-022
- **Definition type:** test function
- **Source:** `tests/test_api.py:446-469`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert response.json()["already_published"] is True
assert response.json()["pin_id"] == "previous-pin-id"
```

## Evidence boundary
Read the complete test body in the current source range. Test doubles and monkeypatches do not establish real Pinterest, Neon, Cloudflare or DeepSeek behavior. No publish-capable test was executed during this audit.

## Exact source

```python
def test_publish_route_does_not_duplicate_successful_pin(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    from app import database
    import app.main as main_module

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_access_token", "test-token")
    monkeypatch.setattr(settings, "pinterest_board_id", "board-7")
    monkeypatch.setattr(database, "get_product", lambda product_id: {"id": product_id})
    monkeypatch.setattr(database, "get_content_version", lambda product_id, version_id: {"id": version_id})
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: {
        "blocked": True, "id": 44, "status": "succeeded", "pinterest_pin_id": "previous-pin-id"
    })
    def must_not_publish(**kwargs):
        raise AssertionError("duplicate Pinterest call should be blocked")
    monkeypatch.setattr(main_module, "publish_image_pin", must_not_publish)
    response = client.post(
        "/publish", json={"product_id": 5, "content_version_id": 12},
        headers={"X-API-Key": "private-test-api-key"},
    )
    assert response.status_code == 200
    assert response.json()["already_published"] is True
    assert response.json()["pin_id"] == "previous-pin-id"


```
