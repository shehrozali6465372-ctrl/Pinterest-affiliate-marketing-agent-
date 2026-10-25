from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
HEADERS = {"X-Credential-Ingest-Key": "ingest-test-secret"}


def test_refresh_endpoint_requires_service_key(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "ingest-test-secret")
    response = client.post(
        "/integrations/pinterest/refresh",
        json={"account_id": "pinterest:123", "client_id": "client-id", "client_secret": "client-secret"},
    )
    assert response.status_code == 401


def test_refresh_endpoint_rotates_and_persists_tokens_without_returning_secrets(monkeypatch):
    import httpx
    from app import credential_vault

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "ingest-test-secret")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(
        credential_vault,
        "get_pinterest_refresh_credential",
        lambda account_id: {
            "account_id": account_id,
            "pinterest_user_id": "123",
            "username": "test-user",
            "refresh_token": "old-refresh-secret",
            "scope": "pins:read,pins:write",
        },
    )
    saved_payloads = []

    def store(payload):
        saved_payloads.append(payload)
        return {"account_id": payload["account_id"], "updated_at": datetime.now(timezone.utc)}

    monkeypatch.setattr(credential_vault, "store_pinterest_credential", store)

    class FakeResponse:
        content = b'{"access_token":"new-access-secret"}'
        is_success = True
        status_code = 200
        def json(self):
            return {
                "access_token": "new-access-secret",
                "refresh_token": "new-refresh-secret",
                "token_type": "bearer",
                "scope": "pins:read,pins:write",
                "expires_in": 1800,
                "refresh_token_expires_in": 86400,
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def post(self, url, *, auth, data):
            assert url == "https://api.pinterest.com/v5/oauth/token"
            assert auth == ("client-id", "client-secret")
            assert data["grant_type"] == "refresh_token"
            assert data["refresh_token"] == "old-refresh-secret"
            assert data["continuous_refresh"] == "true"
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    response = client.post(
        "/integrations/pinterest/refresh",
        headers=HEADERS,
        json={"account_id": "pinterest:123", "client_id": "client-id", "client_secret": "client-secret"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["refreshed"] is True
    assert response.json()["account_id"] == "pinterest:123"
    assert "new-access-secret" not in response.text
    assert "new-refresh-secret" not in response.text
    assert saved_payloads[0]["access_token"] == "new-access-secret"
    assert saved_payloads[0]["refresh_token"] == "new-refresh-secret"
    assert saved_payloads[0]["pinterest_user_id"] == "123"
