from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app import database, workflow


def test_hub_pin_gateway_persists_ledger_and_enforces_disclosure(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "hub-service-test-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-access-token"})

    saved = {}
    def create_product(**kwargs):
        saved.update(kwargs)
        return (
            {"id": 41, "product_name": kwargs["product_name"]},
            {"id": 42, "product_id": 41, "title": kwargs["title"]},
        )

    monkeypatch.setattr(database, "create_product_with_content_version", create_product)
    monkeypatch.setattr(workflow, "begin_publish_attempt", lambda **kwargs: {"blocked": False, "id": 43})
    finish_calls = []
    def finish(publication_id, **kwargs):
        finish_calls.append((publication_id, kwargs))
        return {"id": publication_id, "status": kwargs["status"], "pinterest_pin_id": kwargs["pinterest_pin_id"], "http_status": kwargs["http_status"]}

    monkeypatch.setattr(workflow, "finish_publish_attempt", finish)
    pinterest_calls = []
    def pinterest_request(method, path, token, *, body=None):
        pinterest_calls.append((method, path, token, body))
        if method == "GET":
            return 200, {"id": "123"}
        return 201, {"id": "pin-123", "created_at": "2026-11-01T00:00:00Z"}

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)

    affiliate_url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen"
    response = TestClient(app).post(
        "/workflow/publish-hub-pin",
        headers={
            "X-Credential-Ingest-Key": "hub-service-test-key",
            "Idempotency-Key": "hub-pin-test-0001",
        },
        json={
            "account_id": "pinterest:123",
            "board_id": "board-123",
            "title": "Three-Tier Spice Rack",
            "description": "Organize everyday spices in a compact kitchen.",
            "alt_text": "A three-tier rack holding labeled spice jars.",
            "image_url": "https://images.example.com/spice-rack.jpg",
            "destination_url": affiliate_url,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["published"] is True
    assert body["pin_id"] == "pin-123"
    assert saved["image_url"] == "https://images.example.com/spice-rack.jpg"
    assert saved["affiliate_url"] == affiliate_url
    assert saved["description"].endswith(
        "Affiliate disclosure: This post contains affiliate links; I may earn a commission at no extra cost to you."
    )
    assert pinterest_calls[0][0:3] == ("GET", "/user_account", "test-access-token")
    assert pinterest_calls[1][0:3] == ("POST", "/pins", "test-access-token")
    assert pinterest_calls[1][3]["link"] == affiliate_url
    assert pinterest_calls[1][3]["alt_text"] == "A three-tier rack holding labeled spice jars."
    assert finish_calls[0][0] == 43
    assert finish_calls[0][1]["status"] == "succeeded"


def test_hub_pin_gateway_requires_idempotency_key(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "hub-service-test-key")
    response = TestClient(app).post(
        "/workflow/publish-hub-pin",
        headers={"X-Credential-Ingest-Key": "hub-service-test-key"},
        json={
            "account_id": "pinterest:123",
            "board_id": "board-123",
            "title": "Test Pin",
            "description": "Description",
            "alt_text": "A test image",
            "image_url": "https://images.example.com/test.jpg",
            "destination_url": "https://example.com/product",
        },
    )
    assert response.status_code == 422
