from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


class FakeResponse:
    status_code = 200
    is_success = True
    content = b'{"product_tags":[{"pin_id":"product-1"}]}'

    def json(self):
        return {"product_tags": [{"pin_id": "product-1"}]}


class FakeClient:
    calls = []

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse()


def _configure(monkeypatch):
    import app.credential_vault
    import httpx

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "service-key")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(
        app.credential_vault,
        "get_pinterest_credential",
        lambda _account: {"access_token": "test-token"},
    )
    FakeClient.calls = []
    monkeypatch.setattr(httpx, "Client", FakeClient)


def test_read_product_tags_initializes_query_and_calls_v5_endpoint(monkeypatch):
    _configure(monkeypatch)

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={
            "account_id": "pinterest:123",
            "operation": "product_tags",
            "payload": {"pin_id": "hero-1"},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["product_tags"][0]["pin_id"] == "product-1"
    method, url, kwargs = FakeClient.calls[0]
    assert method == "GET"
    assert url == "https://api.pinterest.com/v5/pins/hero-1/product_tags"
    assert kwargs["params"] is None
    assert kwargs["json"] is None


def test_add_product_tags_uses_official_v5_request_schema(monkeypatch):
    _configure(monkeypatch)

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={
            "account_id": "pinterest:123",
            "operation": "add_product_tags",
            "payload": {"pin_id": "hero-1", "product_pin_ids": ["product-1"]},
        },
    )

    assert response.status_code == 200
    method, url, kwargs = FakeClient.calls[0]
    assert method == "POST"
    assert url == "https://api.pinterest.com/v5/pins/hero-1/product_tags"
    assert kwargs["params"] is None
    assert kwargs["json"] == {"product_tags": [{"pin_id": "product-1"}]}
