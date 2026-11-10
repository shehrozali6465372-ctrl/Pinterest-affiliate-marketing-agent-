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
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key", "Idempotency-Key": "identity-check-001"},
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
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key", "Idempotency-Key": "identity-check-002"},
        json={
            "account_id": "pinterest:123456",
            "operation": "create_board",
            "payload": {"name": "Synthetic test board"},
        },
    )

    assert response.status_code == 409
    assert "identity does not match" in response.json()["detail"]

def test_disconnect_fails_closed_when_stored_credential_identity_is_invalid(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")

    from app import credential_vault

    def reject_invalid_identity(account_id):
        raise ValueError("synthetic identity mismatch")

    monkeypatch.setattr(credential_vault, "revoke_pinterest_credential", reject_invalid_identity)
    response = TestClient(app).post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key"},
        json={
            "account_id": "pinterest:123456",
            "operation": "disconnect",
            "payload": {},
        },
    )

    assert response.status_code == 409
    assert "identity is invalid" in response.json()["detail"]


def test_create_board_requires_idempotency_key(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")
    response = TestClient(app).post(
        "/integrations/pinterest/operation",
        headers={"X-Credential-Ingest-Key": "synthetic-hub-key"},
        json={"account_id": "pinterest:123456", "operation": "create_board",
              "payload": {"name": "Synthetic board"}},
    )
    assert response.status_code == 422


def test_create_board_replays_persisted_success_without_second_provider_write(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")
    from app import credential_vault, database

    monkeypatch.setattr(credential_vault, "get_pinterest_credential", lambda account_id: {
        "account_id": account_id, "pinterest_user_id": "123456",
        "access_token": "synthetic-access-token",
    })
    stored = {"status": "acquired"}
    writes = []
    monkeypatch.setattr(database, "claim_pinterest_board_operation",
                        lambda **kwargs: dict(stored))
    monkeypatch.setattr(database, "complete_pinterest_board_operation",
                        lambda **kwargs: stored.update(status="succeeded", result=kwargs["result"]))
    class IdentityResponse:
        status_code = 200
        is_success = True
        content = b'{"id":"123456"}'
        def json(self): return {"id": "123456"}
    class BoardResponse:
        status_code = 200
        is_success = True
        content = b'{"id":"board-1"}'
        def json(self): return {"id": "board-1"}
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs): return IdentityResponse()
        def request(self, method, url, **kwargs):
            writes.append((method, url))
            return BoardResponse()
    monkeypatch.setattr(httpx, "Client", Client)
    client = TestClient(app)
    request = {"account_id": "pinterest:123456", "operation": "create_board",
               "payload": {"name": "Synthetic board"}}
    headers = {"X-Credential-Ingest-Key": "synthetic-hub-key", "Idempotency-Key": "board-create-001"}
    first = client.post("/integrations/pinterest/operation", headers=headers, json=request)
    assert first.status_code == 200
    stored.update(status="succeeded", result={"id": "board-1"})
    second = client.post("/integrations/pinterest/operation", headers=headers, json=request)
    assert second.status_code == 200
    assert second.json() == {"data": {"id": "board-1"}, "replayed": True}
    assert len(writes) == 1


def test_ambiguous_create_board_timeout_is_marked_uncertain_and_never_retried(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-hub-key")
    from app import credential_vault, database

    monkeypatch.setattr(credential_vault, "get_pinterest_credential", lambda account_id: {
        "account_id": account_id, "pinterest_user_id": "123456",
        "access_token": "synthetic-access-token",
    })
    state = {"status": "acquired"}
    writes = []
    monkeypatch.setattr(database, "claim_pinterest_board_operation", lambda **kwargs: dict(state))
    def mark_uncertain(**kwargs):
        state["status"] = "uncertain"
    monkeypatch.setattr(database, "mark_pinterest_board_operation_uncertain", mark_uncertain)
    class Response:
        status_code = 200
        is_success = True
        content = b'{"id":"123456"}'
        def json(self): return {"id": "123456"}
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs): return Response()
        def request(self, method, url, **kwargs):
            writes.append((method, url))
            raise httpx.ReadTimeout("synthetic timeout after request dispatch")
    monkeypatch.setattr(httpx, "Client", Client)
    client = TestClient(app)
    request = {"account_id": "pinterest:123456", "operation": "create_board",
               "payload": {"name": "Synthetic board"}}
    headers = {"X-Credential-Ingest-Key": "synthetic-hub-key", "Idempotency-Key": "board-create-002"}
    first = client.post("/integrations/pinterest/operation", headers=headers, json=request)
    assert first.status_code == 502
    assert state["status"] == "uncertain"
    second = client.post("/integrations/pinterest/operation", headers=headers, json=request)
    assert second.status_code == 409
    assert "uncertain" in second.json()["detail"].lower()
    assert len(writes) == 1
