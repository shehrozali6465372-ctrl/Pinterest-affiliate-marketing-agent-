from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
API_HEADERS = {"X-API-Key": "diagnostic-test-key"}


def _auth(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "diagnostic-test-key")


def test_pinterest_diagnostic_requires_account_id_and_auth(monkeypatch):
    _auth(monkeypatch)
    assert client.get("/diagnostics/pinterest").status_code == 422
    assert client.get("/diagnostics/pinterest?account_id=pinterest:123").status_code == 401


def test_pinterest_diagnostic_uses_caller_account_id_and_never_generates(monkeypatch):
    _auth(monkeypatch)
    seen = {}

    def fake_get_credential(account_id):
        seen["account_id"] = account_id
        return {"access_token": "never-return-this-token"}

    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers):
            seen["url"] = url
            seen["authorization"] = headers["Authorization"]
            return FakeResponse()

    monkeypatch.setattr("app.credential_vault.get_pinterest_credential", fake_get_credential)
    monkeypatch.setattr("app.diagnostics.httpx.Client", FakeClient)
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:my-account",
        headers=API_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["account_id"] == "pinterest:my-account"
    assert body["side_effects"]["pinterest_pin_created"] is False
    assert body["side_effects"]["ai_generation_called"] is False
    assert seen["account_id"] == "pinterest:my-account"
    assert seen["authorization"] == "Bearer never-return-this-token"
    assert "never-return-this-token" not in response.text


def test_pinterest_diagnostic_reports_missing_credential_without_calling_api(monkeypatch):
    _auth(monkeypatch)

    def missing(_account_id):
        raise LookupError("not connected")

    monkeypatch.setattr("app.credential_vault.get_pinterest_credential", missing)
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:missing",
        headers=API_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["error"] == "credential_not_connected"
    assert response.json()["side_effects"]["pinterest_pin_created"] is False


def test_pinterest_diagnostic_distinguishes_invalid_encryption_key(monkeypatch):
    _auth(monkeypatch)

    def invalid_key(_account_id):
        raise RuntimeError("PINTEREST_TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")

    monkeypatch.setattr("app.credential_vault.get_pinterest_credential", invalid_key)
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:123",
        headers=API_HEADERS,
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "stage": "credential_configuration",
        "error": "token_encryption_key_missing_or_invalid",
    }
    assert "32 bytes" not in response.text


def test_pinterest_diagnostic_sanitizes_upstream_rejection(monkeypatch):
    _auth(monkeypatch)
    monkeypatch.setattr(
        "app.credential_vault.get_pinterest_credential",
        lambda _account_id: {"access_token": "private-token"},
    )

    class FakeResponse:
        is_success = False
        status_code = 401

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers):
            return FakeResponse()

    monkeypatch.setattr("app.diagnostics.httpx.Client", FakeClient)
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:123",
        headers=API_HEADERS,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["stage"] == "pinterest_api"
    assert response.json()["detail"]["upstream_http_status"] == 401
    assert "private-token" not in response.text
