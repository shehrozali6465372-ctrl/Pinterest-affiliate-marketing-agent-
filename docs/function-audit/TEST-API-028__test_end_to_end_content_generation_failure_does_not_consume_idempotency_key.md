# test_end_to_end_content_generation_failure_does_not_consume_idempotency_key

- **Unique ID:** TEST-API-028
- **Definition type:** test function
- **Source:** `tests/test_api.py:566-608`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 503
assert "before product persistence" in response.json()["detail"]
assert persistence_calls == []
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only local behavior under test doubles, not live external integration.

## Exact source

```python
def test_end_to_end_content_generation_failure_does_not_consume_idempotency_key(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow
    from app.content_generation import ContentGenerationError

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token"})
    monkeypatch.setattr(workflow, "_pinterest_request", lambda *args, **kwargs: (200, {"id": "test-user"}))
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/pin.png",
        "model": "test-image-model",
    })

    def fail_generation(**kwargs):
        raise ContentGenerationError("provider temporarily unavailable")

    persistence_calls = []
    monkeypatch.setattr(workflow, "generate_pin_content", fail_generation)
    monkeypatch.setattr(
        workflow, "create_product_with_content_version",
        lambda **kwargs: persistence_calls.append(kwargs),
    )

    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-content-fail",
        },
    )
    assert response.status_code == 503
    assert "before product persistence" in response.json()["detail"]
    assert persistence_calls == []




```
