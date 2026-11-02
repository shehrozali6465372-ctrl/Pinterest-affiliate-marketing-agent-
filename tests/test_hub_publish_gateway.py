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
    gateway_calls = []
    def gateway(**kwargs):
        gateway_calls.append(kwargs)
        return {"published": True, "already_published": False, "pin_id": "pin-123", "publication_id": 43, "board_id": kwargs["board_id"], "http_status": 201}
    monkeypatch.setattr(workflow, "publish_pin_with_ledger", gateway)
    pinterest_calls = []
    def pinterest_request(method, path, token, *, body=None):
        pinterest_calls.append((method, path, token, body))
        return 200, {"id": "123"}

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
    assert len(pinterest_calls) == 1  # account preflight only; shared gateway owns the Pin write
    assert gateway_calls[0]["payload"]["link"] == affiliate_url
    assert gateway_calls[0]["payload"]["alt_text"] == "A three-tier rack holding labeled spice jars."
    assert gateway_calls[0]["access_token"] == "test-access-token"


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
