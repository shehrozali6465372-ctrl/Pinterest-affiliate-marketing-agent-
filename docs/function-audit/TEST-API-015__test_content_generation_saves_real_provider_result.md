# test_content_generation_saves_real_provider_result

- **Unique ID:** TEST-API-015
- **Definition type:** test function
- **Source:** `tests/test_api.py:235-281`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert response.json()["model_id"] == "deepseek-flash"
assert response.json()["description"] == AFFILIATE_DISCLOSURE
assert saved_rows[0]["product_id"] == 5
assert saved_rows[0]["prompt_version"] == "pin-content-v1"
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_content_generation_saves_real_provider_result(monkeypatch):
    from app import database
    import app.main as main_module

    saved_rows = []
    product = {
        "id": 5,
        "product_name": VALID_PRODUCT["product_name"],
        "product_details": VALID_PRODUCT["product_details"],
        "image_url": VALID_PRODUCT["image_url"],
        "affiliate_url": VALID_PRODUCT["affiliate_url"],
    }

    def save_version(**kwargs):
        saved_rows.append(kwargs)
        return {
            "id": 12,
            "product_id": kwargs["product_id"],
            "version_number": 1,
            **kwargs,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "llm_api_key", "test-only-key")
    monkeypatch.setattr(database, "get_product", lambda product_id: product)
    monkeypatch.setattr(database, "create_content_version", save_version)
    monkeypatch.setattr(
        main_module,
        "generate_pin_content",
        lambda **kwargs: (
            GeneratedContent(
                pin_idea="Show the spice rack beside a neatly arranged kitchen counter.",
                title="A Tidy Kitchen Spice Rack",
                description=AFFILIATE_DISCLOSURE,
                alt_text="A wooden spice rack with jars mounted on a kitchen wall.",
            ),
            "deepseek-flash",
        ),
    )
    response = client.post("/products/5/content")
    assert response.status_code == 200
    assert response.json()["model_id"] == "deepseek-flash"
    assert response.json()["description"] == AFFILIATE_DISCLOSURE
    assert saved_rows[0]["product_id"] == 5
    assert saved_rows[0]["prompt_version"] == "pin-content-v1"


```
