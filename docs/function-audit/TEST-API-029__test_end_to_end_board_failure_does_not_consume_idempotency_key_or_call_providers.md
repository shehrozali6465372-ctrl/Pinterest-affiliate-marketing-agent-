# test_end_to_end_board_failure_does_not_consume_idempotency_key_or_call_providers

- **Unique ID:** TEST-API-029
- **Definition type:** test function
- **Source:** `tests/test_api.py:610-648`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 502
assert provider_calls == []
assert persistence_calls == []
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only local behavior under test doubles, not live external integration.

## Exact source

```python
def test_end_to_end_board_failure_does_not_consume_idempotency_key_or_call_providers(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token"})

    def pinterest_request(method, path, token, *, body=None):
        if method == "GET" and path == "/user_account":
            return 200, {"id": "test-user"}
        if method == "GET" and path == "/boards?page_size=100":
            raise HTTPException(status_code=502, detail="Pinterest unavailable")
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    provider_calls = []
    persistence_calls = []
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", lambda **kwargs: provider_calls.append("image"))
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: provider_calls.append("content"))
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: persistence_calls.append(kwargs))

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
            "Idempotency-Key": "request-key-board-fail",
        },
    )
    assert response.status_code == 502
    assert provider_calls == []
    assert persistence_calls == []


```
