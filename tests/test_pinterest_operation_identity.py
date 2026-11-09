"""Synthetic regression tests for Pinterest account-operation identity checks."""
import httpx
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_account_operation_rejects_token_identity_mismatch_before_board_write(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")

    from app import credential_vault

    monkeypatch.setattr(
        credential_vault,
        "get_pinterest_credential",
        lambda account_id: {
            "account_id": account_id,
            "pinterest_user_id": "123456",
            "access_token": "synthetic-access-token",
        },
    )

    calls = []

    class FakeResponse:
        status_code = 200
        is_success = True
        content = b'{"id":"999999"}'

        def json(self):
            return {"id": "999999"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            calls.append(("GET", args[0]))
            return FakeResponse()

        def request(self, method, url, **kwargs):
            calls.append((method, url))
            raise AssertionError("Pinterest operation must not run after identity mismatch")

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = TestClient(app)
    response = client.post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key"},
        json={
            "account_id": "pinterest:123456",
            "operation": "create_board",
            "payload": {"name": "Synthetic test board"},
        },
    )

    assert response.status_code == 409
    assert "identity does not match" in response.json()["detail"]
    assert len(calls) == 1
    assert calls[0][0] == "GET"


def test_account_operation_rejects_mismatched_stored_account_metadata_before_network(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")

    from app import credential_vault

    monkeypatch.setattr(
        credential_vault,
        "get_pinterest_credential",
        lambda account_id: {
            "account_id": account_id,
            "pinterest_user_id": "different-user",
            "access_token": "synthetic-access-token",
        },
    )

    def unexpected_client(*args, **kwargs):
        raise AssertionError("network must not be contacted for mismatched stored metadata")

    monkeypatch.setattr(httpx, "Client", unexpected_client)
    response = TestClient(app).post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key"},
        json={
            "account_id": "pinterest:123456",
            "operation": "create_board",
            "payload": {"name": "Synthetic test board"},
        },
    )

    assert response.status_code == 409
    assert "identity does not match" in response.json()["detail"]
