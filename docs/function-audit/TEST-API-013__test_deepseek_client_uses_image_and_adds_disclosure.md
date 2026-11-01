# test_deepseek_client_uses_image_and_adds_disclosure

- **Unique ID:** TEST-API-013
- **Definition type:** test function
- **Source:** `tests/test_api.py:162-216`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert model == "deepseek-flash"
assert calls["endpoint"] == "https://api.deepseek.com/chat/completions"
assert calls["headers"]["Authorization"] == "Bearer unit-test-secret"
assert isinstance(message_content, list)
assert message_content[0]["type"] == "text"
assert "visible image content" in message_content[0]["text"]
assert message_content[1]["type"] == "image_url"
assert message_content[1]["image_url"]["url"] == VALID_PRODUCT["image_url"]
assert AFFILIATE_DISCLOSURE in content.description
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_deepseek_client_uses_image_and_adds_disclosure(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "pin_idea": "Style the rack on an organized counter.",
                            "title": "Organized Spice Rack",
                            "description": "A tidy way to arrange everyday spices.",
                            "alt_text": "Wooden rack holding spice jars on a kitchen wall.",
                        })
                    }
                }]
            }

    class FakeClient:
        def __init__(self, timeout):
            calls["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.update(endpoint=endpoint, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)
    content, model = generate_pin_content(
        product_name=VALID_PRODUCT["product_name"],
        product_details=VALID_PRODUCT["product_details"],
        image_url=VALID_PRODUCT["image_url"],
    )
    assert model == "deepseek-flash"
    assert calls["endpoint"] == "https://api.deepseek.com/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer unit-test-secret"
    message_content = calls["payload"]["messages"][1]["content"]
    assert isinstance(message_content, list)
    assert message_content[0]["type"] == "text"
    assert "visible image content" in message_content[0]["text"]
    assert message_content[1]["type"] == "image_url"
    assert message_content[1]["image_url"]["url"] == VALID_PRODUCT["image_url"]
    assert AFFILIATE_DISCLOSURE in content.description


```
