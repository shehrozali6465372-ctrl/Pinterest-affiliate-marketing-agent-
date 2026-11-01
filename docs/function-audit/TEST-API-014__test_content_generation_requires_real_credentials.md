# test_content_generation_requires_real_credentials

- **Unique ID:** TEST-API-014
- **Definition type:** test function
- **Source:** `tests/test_api.py:218-233`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 503
assert "LLM_API_KEY is not configured" in response.json()["detail"]
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_content_generation_requires_real_credentials(monkeypatch):
    from app import database

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(database, "get_product", lambda product_id: {
        "id": product_id,
        "product_name": VALID_PRODUCT["product_name"],
        "product_details": VALID_PRODUCT["product_details"],
        "image_url": VALID_PRODUCT["image_url"],
        "affiliate_url": VALID_PRODUCT["affiliate_url"],
    })
    response = client.post("/products/1/content")
    assert response.status_code == 503
    assert "LLM_API_KEY is not configured" in response.json()["detail"]


```
