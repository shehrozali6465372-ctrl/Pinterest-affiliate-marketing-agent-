# test_end_to_end_publish_rejects_reused_idempotency_key

- **Unique ID:** TEST-API-026
- **Definition type:** test function
- **Source:** `tests/test_api.py:504-530`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 409
assert response.json()["detail"]["code"] == "idempotency_key_reused"
```

## Evidence boundary
Read the complete test body in the current source range. Test doubles and monkeypatches do not establish real Pinterest, Neon, Cloudflare or DeepSeek behavior. No publish-capable test was executed during this audit.

## Exact source

```python
def test_end_to_end_publish_rejects_reused_idempotency_key(monkeypatch):
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(
        workflow,
        "get_product_by_idempotency_key",
        lambda key: {"id": 123, "product_name": "Previously accepted"},
    )
    payload = {
        "product_name": "Copco 3-Tier Spice Rack Organizer",
        "product_details": "Three-tier spice rack organizer.",
        "affiliate_url": "https://example.com/affiliate",
        "account_id": "pinterest:test-account",
    }
    response = client.post(
        "/workflow/publish-product",
        json=payload,
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-12345",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_reused"



```
