# test_end_to_end_workflow_uses_atomic_persistence_and_records_real_pin_id

- **Unique ID:** TEST-API-030
- **Definition type:** test function
- **Source:** `tests/test_api.py:650-718`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS REVIEWED; NOT EXECUTED IN THIS AUDIT

## Behavior
Mocks board lookup, media/content providers, atomic DB persistence and Pinterest response. Asserts affiliate link is sent, successful response contains returned Pin identifier, and one idempotent persistence record is written.

## Exact source

```python
def test_end_to_end_workflow_uses_atomic_persistence_and_records_real_pin_id(monkeypatch):
    from types import SimpleNamespace
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token"})
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/pin.png",
        "model": "test-image-model",
    })
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: (
        SimpleNamespace(
            pin_idea="Organized kitchen shelf",
            title="Kitchen Spice Rack Organization",
            description="Organize spices. Affiliate disclosure: This post contains affiliate links; I may earn a commission at no extra cost to you.",
            alt_text="A spice rack organizer.",
        ),
        "deepseek-test-model",
    ))
    persistence = []
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        persistence.append(kwargs) or (
            {"id": 101, "product_name": kwargs["product_name"]},
            {"id": 202, "product_id": 101},
        )
    ))
    monkeypatch.setattr(workflow, "begin_publish_attempt", lambda **kwargs: {
        "blocked": False, "id": 303, "status": "pending",
    })
    monkeypatch.setattr(workflow, "finish_publish_attempt", lambda publication_id, **kwargs: {
        "id": publication_id, "status": kwargs["status"],
        "pinterest_pin_id": kwargs.get("pinterest_pin_id"), "http_status": kwargs.get("http_status"),
    })

    def pinterest_request(method, path, token, *, body=None):
        if method == "GET" and path == "/user_account":
            return 200, {"id": "test-user"}
        if method == "GET" and path == "/boards?page_size=100":
            return 200, {"items": []}
        if method == "POST" and path == "/boards":
            return 201, {"id": "board-404"}
        if method == "POST" and path == "/pins":
            assert body["link"] == "https://example.com/affiliate"
            return 201, {"id": "pin-505", "created_at": "2026-10-25T00:00:00Z"}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
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
            "Idempotency-Key": "request-key-success-123",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["pin_id"] == "pin-505"
    assert response.json()["published"] is True
    assert len(persistence) == 1
    assert persistence[0]["idempotency_key"] == "request-key-success-123"


```

## Evidence boundary
The test uses FastAPI TestClient and mocked provider/database dependencies. Its assertions do not establish live Pinterest, DeepSeek, Cloudflare or Neon behavior. In particular, any Pin identifier is supplied by the fake provider response, not created in Pinterest.
