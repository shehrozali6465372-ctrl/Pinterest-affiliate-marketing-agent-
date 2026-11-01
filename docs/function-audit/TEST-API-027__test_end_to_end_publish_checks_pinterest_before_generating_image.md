# test_end_to_end_publish_checks_pinterest_before_generating_image

- **Unique ID:** TEST-API-027
- **Definition type:** test function
- **Source:** `tests/test_api.py:532-564`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 401
assert "Stored Pinterest credential could not be verified" in response.json()["detail"]
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only local behavior under test doubles, not live external integration.

## Exact source

```python
def test_end_to_end_publish_checks_pinterest_before_generating_image(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token"})

    def reject_token(*args, **kwargs):
        raise HTTPException(status_code=401, detail="invalid token")

    def should_not_generate_image(**kwargs):
        raise AssertionError("image generation must not run for an invalid Pinterest token")

    monkeypatch.setattr(workflow, "_pinterest_request", reject_token)
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", should_not_generate_image)
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
            "Idempotency-Key": "request-key-12345",
        },
    )
    assert response.status_code == 401
    assert "Stored Pinterest credential could not be verified" in response.json()["detail"]



```
