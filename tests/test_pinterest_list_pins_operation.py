from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


class FakeResponse:
    status_code = 200
    is_success = True
    content = b'{"items":[{"id":"pin-123","title":"Existing Pin"}],"bookmark":"next-page"}'

    def json(self):
        return {"items": [{"id": "pin-123", "title": "Existing Pin"}], "bookmark": "next-page"}


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


def test_list_pins_operation_is_read_only_and_passes_pagination(monkeypatch):
    import app.credential_vault
    import httpx

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "service-key")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(app.credential_vault, "get_pinterest_credential", lambda _account: {"access_token": "test-token"})
    FakeClient.calls = []
    monkeypatch.setattr(httpx, "Client", FakeClient)

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={"account_id": "pinterest:123", "operation": "list_pins", "payload": {"page_size": 50, "bookmark": "cursor-1"}},
    )

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["id"] == "pin-123"
    assert FakeClient.calls[0][0] == "GET"
    assert FakeClient.calls[0][1] == "https://api.pinterest.com/v5/pins"
    assert FakeClient.calls[0][2]["params"] == {"page_size": 50, "bookmark": "cursor-1"}
    assert FakeClient.calls[0][2]["json"] is None


def test_list_pins_rejects_invalid_page_size_before_provider_call(monkeypatch):
    import app.credential_vault

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "service-key")
    monkeypatch.setattr(app.credential_vault, "get_pinterest_credential", lambda _account: {"access_token": "test-token"})
    FakeClient.calls = []

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={"account_id": "pinterest:123", "operation": "list_pins", "payload": {"page_size": 1000}},
    )

    assert response.status_code == 422
    assert FakeClient.calls == []


def test_list_pins_can_include_protected_pins_and_product_tag_objects(monkeypatch):
    import app.credential_vault
    import httpx

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "service-key")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(app.credential_vault, "get_pinterest_credential", lambda _account: {"access_token": "test-token"})
    FakeClient.calls = []
    monkeypatch.setattr(httpx, "Client", FakeClient)

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={"account_id": "pinterest:123", "operation": "list_pins", "payload": {
            "page_size": 100, "include_protected_pins": True, "include_product_tag_obj": True,
        }},
    )

    assert response.status_code == 200
    assert FakeClient.calls[0][2]["params"] == {
        "page_size": 100, "include_protected_pins": True, "include_product_tag_obj": True,
    }


def test_list_pins_rejects_non_boolean_protected_filter_before_provider_call(monkeypatch):
    import app.credential_vault
    import httpx

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "service-key")
    monkeypatch.setattr(app.credential_vault, "get_pinterest_credential", lambda _account: {"access_token": "test-token"})
    FakeClient.calls = []
    monkeypatch.setattr(httpx, "Client", FakeClient)

    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "service-key"},
        json={"account_id": "pinterest:123", "operation": "list_pins", "payload": {
            "include_protected_pins": "true",
        }},
    )

    assert response.status_code == 422
    assert FakeClient.calls == []
