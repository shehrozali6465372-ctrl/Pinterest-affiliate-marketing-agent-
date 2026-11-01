# test_publish_route_persists_confirmed_pin_id

- **Unique ID:** TEST-API-021
- **Definition type:** test function
- **Source:** `tests/test_api.py:402-444`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert response.json()["published"] is True
assert response.json()["pin_id"] == "verified-pin-id"
```

## Evidence boundary
Read the complete test body in the current source range. Test doubles and monkeypatches do not establish real Pinterest, Neon, Cloudflare or DeepSeek behavior. No publish-capable test was executed during this audit.

## Exact source

```python
def test_publish_route_persists_confirmed_pin_id(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    from app import database
    import app.main as main_module

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_access_token", "test-token")
    monkeypatch.setattr(settings, "pinterest_board_id", "board-7")
    product = {"id": 5, **VALID_PRODUCT}
    content = {
        "id": 12, "product_id": 5, "title": "Kitchen Spice Rack",
        "description": AFFILIATE_DISCLOSURE, "alt_text": "A wooden spice rack.",
    }
    attempt = {"blocked": False, "id": 44, "status": "pending"}
    monkeypatch.setattr(database, "get_product", lambda product_id: product)
    monkeypatch.setattr(database, "get_content_version", lambda product_id, version_id: content)
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: attempt)
    monkeypatch.setattr(
        main_module,
        "publish_image_pin",
        lambda **kwargs: {
            "pin_id": "verified-pin-id", "http_status": 201,
            "metadata": {"id": "verified-pin-id", "board_id": "board-7"},
        },
    )
    monkeypatch.setattr(
        database,
        "finish_publish_attempt",
        lambda publication_id, **kwargs: {
            "id": publication_id,
            "status": kwargs["status"],
            "pinterest_pin_id": kwargs["pinterest_pin_id"],
            "http_status": kwargs["http_status"],
        },
    )
    response = client.post(
        "/publish", json={"product_id": 5, "content_version_id": 12},
        headers={"X-API-Key": "private-test-api-key"},
    )
    assert response.status_code == 200
    assert response.json()["published"] is True
    assert response.json()["pin_id"] == "verified-pin-id"


```
