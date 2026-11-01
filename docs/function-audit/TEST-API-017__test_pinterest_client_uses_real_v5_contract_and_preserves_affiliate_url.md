# test_pinterest_client_uses_real_v5_contract_and_preserves_affiliate_url

- **Unique ID:** TEST-API-017
- **Definition type:** test function
- **Source:** `tests/test_api.py:302-342`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert calls["endpoint"] == "https://api.pinterest.com/v5/pins"
assert calls["headers"]["Authorization"] == "Bearer unit-test-token"
assert calls["payload"]["media_source"]["url"] == VALID_PRODUCT["image_url"]
assert calls["payload"]["link"] == affiliate_url
assert result["pin_id"] == "pin-123"
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_pinterest_client_uses_real_v5_contract_and_preserves_affiliate_url(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", "unit-test-token")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    affiliate_url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen"
    calls = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "pin-123", "board_id": "board-7", "created_at": "2026-10-24T00:00:00Z"}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.update(endpoint=endpoint, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    result = publish_image_pin(
        board_id="board-7",
        title="A Tidy Kitchen",
        description=AFFILIATE_DISCLOSURE,
        alt_text="Wooden spice rack fixed to a kitchen wall.",
        image_url=VALID_PRODUCT["image_url"],
        affiliate_url=affiliate_url,
    )
    assert calls["endpoint"] == "https://api.pinterest.com/v5/pins"
    assert calls["headers"]["Authorization"] == "Bearer unit-test-token"
    assert calls["payload"]["media_source"]["url"] == VALID_PRODUCT["image_url"]
    assert calls["payload"]["link"] == affiliate_url
    assert result["pin_id"] == "pin-123"


```
