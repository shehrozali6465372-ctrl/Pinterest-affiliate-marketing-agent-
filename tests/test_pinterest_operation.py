import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
HEADERS = {"X-Credential-Ingest-Key": "product-tag-operation-test-key"}


class FakeResponse:
    is_success = True
    content = b'{"product_tags":[{"pin_id":"product-123"}]}'

    def json(self):
        return {"product_tags": [{"pin_id": "product-123"}]}


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


@pytest.fixture(autouse=True)
def configure_operation(monkeypatch):
    import app.credential_vault

    FakeClient.calls = []
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "product-tag-operation-test-key")
    monkeypatch.setattr(
        app.credential_vault,
        "get_pinterest_credential",
        lambda _account_id: {"access_token": "test-access-token"},
    )
    monkeypatch.setattr("httpx.Client", FakeClient)


def test_product_tags_read_operation_initializes_query_before_request():
    response = client.post(
        "/integrations/pinterest/operation",
        headers=HEADERS,
        json={
            "account_id": "pinterest:123",
            "operation": "product_tags",
            "payload": {"pin_id": "hero-123"},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["product_tags"] == [{"pin_id": "product-123"}]
    method, url, kwargs = FakeClient.calls[0]
    assert method == "GET"
    assert url.endswith("/pins/hero-123/product_tags")
    assert kwargs["params"] is None


def test_add_product_tags_operation_initializes_query_before_request():
    response = client.post(
        "/integrations/pinterest/operation",
        headers=HEADERS,
        json={
            "account_id": "pinterest:123",
            "operation": "add_product_tags",
            "payload": {"pin_id": "hero-123", "product_pin_ids": ["product-123"]},
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["product_tags"] == [{"pin_id": "product-123"}]
    method, url, kwargs = FakeClient.calls[0]
    assert method == "POST"
    assert url.endswith("/pins/hero-123/product_tags")
    assert kwargs["params"] is None
    assert kwargs["json"] == {"product_tags": [{"pin_id": "product-123"}]}
