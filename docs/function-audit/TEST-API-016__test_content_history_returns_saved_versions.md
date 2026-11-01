# test_content_history_returns_saved_versions

- **Unique ID:** TEST-API-016
- **Definition type:** test function
- **Source:** `tests/test_api.py:283-300`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert response.json()["versions"][0]["version_number"] == 2
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_content_history_returns_saved_versions(monkeypatch):
    from app import database

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(database, "get_product", lambda product_id: {"id": product_id})
    monkeypatch.setattr(database, "list_content_versions", lambda product_id: [
        {
            "id": 22, "product_id": product_id, "version_number": 2,
            "provider": "deepseek", "model_id": "deepseek-flash",
            "prompt_version": "pin-content-v1", "pin_idea": "A kitchen pin",
            "title": "Tidy Kitchen", "description": AFFILIATE_DISCLOSURE,
            "alt_text": "A spice rack", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    ])
    response = client.get("/products/5/content")
    assert response.status_code == 200
    assert response.json()["versions"][0]["version_number"] == 2


```
