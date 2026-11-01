# test_end_to_end_publish_requires_idempotency_key

- **Unique ID:** TEST-API-025
- **Definition type:** test function
- **Source:** `tests/test_api.py:484-502`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert missing_key.status_code == 422
assert short_key.status_code == 422
```

## Evidence boundary
Read the complete test body in the current source range. Test doubles and monkeypatches do not establish real Pinterest, Neon, Cloudflare or DeepSeek behavior. No publish-capable test was executed during this audit.

## Exact source

```python
def test_end_to_end_publish_requires_idempotency_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    payload = {
        "product_name": "Copco 3-Tier Spice Rack Organizer",
        "product_details": "Three-tier spice rack organizer.",
        "affiliate_url": "https://example.com/affiliate",
        "account_id": "pinterest:test-account",
    }
    headers = {"X-API-Key": "private-test-api-key"}
    missing_key = client.post("/workflow/publish-product", json=payload, headers=headers)
    assert missing_key.status_code == 422

    short_key = client.post(
        "/workflow/publish-product",
        json=payload,
        headers={**headers, "Idempotency-Key": "short"},
    )
    assert short_key.status_code == 422


```
