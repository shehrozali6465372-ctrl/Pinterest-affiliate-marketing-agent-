"""Mock-only regression tests for the Hub manual Pin publication gateway."""
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)
PAYLOAD = {
    "account_id": "pinterest:test-account",
    "board_id": "board-123",
    "title": "Kitchen Spice Rack Organization",
    "description": "A tidy kitchen idea.",
    "image_url": "https://cdn.example.test/spice-rack.png",
    "destination_url": "https://example.test/product?tag=affiliate-20",
}


@pytest.fixture
def gateway(monkeypatch):
    import app.credential_vault as vault
    import app.database as database
    import httpx

    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "test-ingest-key")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.test/v5")
    monkeypatch.setattr(vault, "get_pinterest_credential", lambda account_id: {
        "account_id": account_id, "pinterest_user_id": "test-account",
        "access_token": "mock-only-token",
    })
    monkeypatch.setattr(database, "persist_manual_publish_draft", lambda **kw: (
        {"id": 10}, {"id": 20}, True,
    ))
    attempts = []
    finishes = []

    def begin(**kw):
        attempts.append(kw)
        return {"id": 30, "blocked": False, "status": "pending"}

    def finish(publication_id, **kw):
        finishes.append((publication_id, kw))
        return {"id": publication_id, "status": kw["status"],
                "pinterest_pin_id": kw.get("pinterest_pin_id"),
                "http_status": kw.get("http_status")}

    monkeypatch.setattr(database, "begin_publish_attempt", begin)
    monkeypatch.setattr(database, "finish_publish_attempt", finish)

    class Response:
        def __init__(self, status, data):
            self.status_code = status
            self.is_success = 200 <= status < 300
            self.content = b"{}"
            self._data = data

        def json(self):
            return self._data

    class FakeClient:
        calls = []

        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            if url.endswith("/user_account"):
                return Response(200, {"id": "test-account"})
            if url.endswith("/boards?page_size=100"):
                return Response(200, {"items": [{"id": "board-123"}]})
            raise AssertionError(url)

        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return Response(201, {"id": "pin-456", "created_at": "2026-11-05T10:00:00Z"})

    monkeypatch.setattr(httpx, "Client", FakeClient)
    return {"attempts": attempts, "finishes": finishes, "http": FakeClient}


def test_manual_publish_gateway_uses_credential_ledger_and_mock_pinterest(gateway):
    response = client.post(
        "/integrations/pinterest/publish-manual",
        json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0001"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["published"] is True
    assert body["pin_id"] == "pin-456"
    assert body["product_id"] == 10
    assert body["content_version_id"] == 20
    assert gateway["attempts"] == [{
        "product_id": 10, "content_version_id": 20,
        "board_id": "board-123", "account_id": "pinterest:test-account",
    }]
    assert gateway["finishes"][0][1]["status"] == "succeeded"
    assert gateway["finishes"][0][1]["pinterest_pin_id"] == "pin-456"
    assert len(gateway["http"].calls) == 3
    assert gateway["http"].calls[-1][2]["json"]["link"] == PAYLOAD["destination_url"]


def test_manual_publish_gateway_requires_service_auth():
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"Idempotency-Key": "manual-pin-key-0002"},
    )
    assert response.status_code == 401


def test_manual_publish_gateway_does_not_retry_unknown_publication(gateway, monkeypatch):
    import app.database as database

    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kw: {
        "id": 31, "blocked": True, "status": "unknown",
    })
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0003"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["status"] == "unknown"
    assert not any(call[0] == "POST" and call[1].endswith("/pins")
                   for call in gateway["http"].calls)


def test_manual_publish_gateway_rejects_generic_create_pin_operation(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "test-ingest-key")
    response = client.post(
        "/integrations/pinterest/operation",
        json={"account_id": "pinterest:test-account", "operation": "create_pin",
              "payload": {"board_id": "board-123"}},
        headers={"X-Credential-Ingest-Key": "test-ingest-key"},
    )
    assert response.status_code == 400


def test_manual_publish_gateway_marks_transport_timeout_unknown(gateway, monkeypatch):
    import httpx
    import app.database as database

    class TimeoutClient(gateway["http"]):
        def post(self, url, **kwargs):
            raise httpx.ReadTimeout("simulated network timeout")

    monkeypatch.setattr(httpx, "Client", TimeoutClient)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0004"},
    )
    assert response.status_code == 502
    assert "uncertain" in response.json()["detail"]
    assert gateway["finishes"][-1][1]["status"] == "unknown"
    assert gateway["finishes"][-1][1]["error_code"] == "transport_outcome_unknown"


def test_manual_publish_gateway_rejects_idempotency_key_payload_mismatch(gateway, monkeypatch):
    import app.database as database

    def mismatch(**kwargs):
        raise ValueError("idempotency_key_payload_mismatch")

    monkeypatch.setattr(database, "persist_manual_publish_draft", mismatch)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0005"},
    )
    assert response.status_code == 409
    assert "different Pin data" in response.json()["detail"]
    assert gateway["attempts"] == []


def test_manual_publish_gateway_fails_closed_when_credential_vault_unavailable(gateway, monkeypatch):
    import app.credential_vault as vault

    def vault_error(account_id):
        raise RuntimeError("simulated encryption configuration failure")

    monkeypatch.setattr(vault, "get_pinterest_credential", vault_error)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0006"},
    )
    assert response.status_code == 503
    assert "no Pin publish request was sent" in response.json()["detail"]
    assert gateway["attempts"] == []
    assert gateway["http"].calls == []


def test_manual_publish_gateway_validates_media_before_reserving_ledger(gateway, monkeypatch):
    import app.pinterest as pinterest

    def invalid_media(_image_url):
        raise pinterest.PinterestPublishError(
            "malformed image", outcome_uncertain=False, error_code="invalid_image_data"
        )

    monkeypatch.setattr(pinterest, "image_media_source", invalid_media)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0007"},
    )
    assert response.status_code == 422
    assert "no Pin publish request was sent" in response.json()["detail"]
    assert gateway["attempts"] == []
    assert gateway["http"].calls == []


def test_manual_publish_gateway_rejects_credential_account_identity_mismatch(gateway, monkeypatch):
    import app.credential_vault as vault

    monkeypatch.setattr(vault, "get_pinterest_credential", lambda account_id: {
        "account_id": account_id, "pinterest_user_id": "different-user",
        "access_token": "mock-only-token",
    })
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0008"},
    )
    assert response.status_code == 409
    assert "identity does not match" in response.json()["detail"]
    assert len(gateway["http"].calls) == 1
    assert gateway["http"].calls[0][0] == "GET"
    assert gateway["attempts"] == []



def test_gateway_marks_success_without_pin_id_as_unknown(gateway, monkeypatch):
    import httpx
    import app.database as database

    # Keep the same fake transport but return a successful response without an ID.
    class Response:
        status_code = 201
        is_success = True
        content = b"{}"
        def json(self):
            return {}

    class MissingIdClient(gateway["http"]):
        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return Response()

    monkeypatch.setattr(httpx, "Client", MissingIdClient)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-0009"},
    )
    assert response.status_code == 502
    assert "outcome is uncertain" in response.json()["detail"]
    assert gateway["finishes"][-1][1]["status"] == "unknown"
    assert gateway["finishes"][-1][1]["error_code"] == "missing_pin_id"


def test_all_pin_creation_http_posts_are_owned_by_shared_gateway():
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    occurrences = []
    for path in app_dir.glob("*.py"):
        source = path.read_text()
        if 'f"{base}/pins"' in source or "publish_image_pin" in source:
            occurrences.append(path.name)
    assert occurrences == ["publishing_gateway.py"]


def test_manual_gateway_treats_pinterest_5xx_as_unknown(gateway, monkeypatch):
    import httpx

    class ServerErrorClient(gateway["http"]):
        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            class Response:
                status_code = 503
                is_success = False
                content = b"{}"
                def json(self): return {"code": "upstream_error"}
            return Response()

    monkeypatch.setattr(httpx, "Client", ServerErrorClient)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-5xx01"},
    )
    assert response.status_code == 502
    assert gateway["finishes"][-1][1]["status"] == "unknown"
    assert gateway["finishes"][-1][1]["error_code"] == "pinterest_server_outcome_unknown"


def test_manual_gateway_records_definite_provider_rejection_as_failed(gateway, monkeypatch):
    import httpx

    class RejectedClient(gateway["http"]):
        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            class Response:
                status_code = 400
                is_success = False
                content = b"{}"
                def json(self): return {"code": "invalid_request"}
            return Response()

    monkeypatch.setattr(httpx, "Client", RejectedClient)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-40001"},
    )
    assert response.status_code == 502
    assert gateway["finishes"][-1][1]["status"] == "failed"
    assert gateway["finishes"][-1][1]["error_code"] == "pinterest_request_rejected"


def test_manual_gateway_keeps_pending_reservation_when_success_ledger_write_fails(gateway, monkeypatch):
    import app.database as database
    import httpx

    def fail_success_write(publication_id, **kwargs):
        raise RuntimeError("simulated ledger outage after provider success")

    monkeypatch.setattr(database, "finish_publish_attempt", fail_success_write)
    response = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-ledger01"},
    )
    assert response.status_code == 503
    assert "Do not retry" in response.json()["detail"]
    assert any(call[0] == "POST" and call[1].endswith("/pins")
               for call in gateway["http"].calls)

    # A subsequent request is blocked by the still-pending durable reservation.
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kw: {
        "id": 30, "blocked": True, "status": "pending",
    })
    before = len([call for call in gateway["http"].calls if call[0] == "POST" and call[1].endswith("/pins")])
    retry = client.post(
        "/integrations/pinterest/publish-manual", json=PAYLOAD,
        headers={"X-Credential-Ingest-Key": "test-ingest-key",
                 "Idempotency-Key": "manual-pin-key-ledger01"},
    )
    after = len([call for call in gateway["http"].calls if call[0] == "POST" and call[1].endswith("/pins")])
    assert retry.status_code == 409
    assert after == before
