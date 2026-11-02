"""Unit tests for the shared Pin publication ledger gateway."""

import pytest

import app.publishing as publishing
from app.pinterest import PinterestPublishError


def _payload():
    return {
        "board_id": "board-1",
        "title": "A valid Pin title",
        "description": "A valid Pin description",
        "alt_text": "A valid description of the image",
        "media_source": {"source_type": "image_url", "url": "https://cdn.example.com/pin.jpg", "is_standard": True},
        "link": "https://example.com/affiliate?tag=home-20",
    }


def _call():
    return publishing.publish_pin_with_ledger(
        product_id=10,
        content_version_id=20,
        board_id="board-1",
        account_id="pinterest:account-1",
        access_token="vault-token",
        payload=_payload(),
    )


def test_shared_gateway_reserves_publishes_and_records_account(monkeypatch):
    reserved = []
    finished = []
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: (
        reserved.append(kwargs) or {"blocked": False, "id": 99, "status": "pending"}
    ))
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (
        201, {"id": "pin-123", "board_id": "board-1", "created_at": "2026-11-02T00:00:00Z"}
    ))
    monkeypatch.setattr(publishing, "finish_publish_attempt", lambda publication_id, **kwargs: (
        finished.append((publication_id, kwargs)) or {
            "id": publication_id, "status": kwargs["status"],
            "pinterest_pin_id": kwargs["pinterest_pin_id"], "http_status": kwargs["http_status"],
        }
    ))

    result = _call()

    assert result["published"] is True
    assert result["pin_id"] == "pin-123"
    assert reserved[0]["account_id"] == "pinterest:account-1"
    assert finished[0][0] == 99
    assert finished[0][1]["status"] == "succeeded"
    assert finished[0][1]["pinterest_pin_id"] == "pin-123"


def test_shared_gateway_never_retries_succeeded_publication(monkeypatch):
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {
        "blocked": True, "id": 99, "status": "succeeded", "pinterest_pin_id": "existing-pin",
    })
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: pytest.fail("must not create a duplicate Pin"))

    result = _call()

    assert result["already_published"] is True
    assert result["pin_id"] == "existing-pin"


def test_shared_gateway_blocks_pending_or_unknown_publication(monkeypatch):
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {
        "blocked": True, "id": 99, "status": "unknown", "pinterest_pin_id": None,
    })
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: pytest.fail("must not retry uncertain Pin"))

    with pytest.raises(publishing.PublicationConflict):
        _call()


def test_shared_gateway_marks_transport_failure_unknown(monkeypatch):
    finished = []
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {"blocked": False, "id": 99})
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (_ for _ in ()).throw(
        PinterestPublishError("transport failed", outcome_uncertain=True, error_code="transport_outcome_unknown")
    ))
    monkeypatch.setattr(publishing, "finish_publish_attempt", lambda publication_id, **kwargs: (
        finished.append(kwargs) or {"id": publication_id, **kwargs}
    ))

    with pytest.raises(PinterestPublishError):
        _call()

    assert finished[0]["status"] == "unknown"
    assert finished[0]["error_code"] == "transport_outcome_unknown"


def test_shared_gateway_marks_provider_rejection_failed(monkeypatch):
    finished = []
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {"blocked": False, "id": 99})
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (_ for _ in ()).throw(
        PinterestPublishError("rejected", outcome_uncertain=False, http_status=400, error_code="pinterest_http_400")
    ))
    monkeypatch.setattr(publishing, "finish_publish_attempt", lambda publication_id, **kwargs: (
        finished.append(kwargs) or {"id": publication_id, **kwargs}
    ))

    with pytest.raises(PinterestPublishError):
        _call()

    assert finished[0]["status"] == "failed"
    assert finished[0]["http_status"] == 400


def test_shared_gateway_marks_unknown_if_success_ledger_write_fails(monkeypatch):
    finish_calls = []
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {"blocked": False, "id": 99})
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (201, {"id": "created-pin"}))
    def finish(publication_id, **kwargs):
        finish_calls.append(kwargs)
        if kwargs["status"] == "succeeded":
            raise RuntimeError("database unavailable")
        return {"id": publication_id, **kwargs}
    monkeypatch.setattr(publishing, "finish_publish_attempt", finish)

    with pytest.raises(publishing.PublicationPersistenceError):
        _call()

    assert [call["status"] for call in finish_calls] == ["succeeded", "unknown"]


def test_shared_gateway_does_not_reuse_another_account_publication(monkeypatch):
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {
        "blocked": True, "account_mismatch": True, "id": 99,
        "status": "succeeded", "account_id": "pinterest:other-account",
        "pinterest_pin_id": "foreign-account-pin",
    })
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: pytest.fail("must not publish across accounts"))

    with pytest.raises(publishing.PublicationConflict):
        _call()


def test_uncertain_success_recording_does_not_overwrite_a_committed_success(monkeypatch):
    state = {"status": "pending", "pin_id": None}
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: {"blocked": False, "id": 99})
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (201, {"id": "committed-pin"}))
    def finish(publication_id, **kwargs):
        if state["status"] != "pending":
            raise RuntimeError("attempt already terminal")
        state["status"] = kwargs["status"]
        state["pin_id"] = kwargs.get("pinterest_pin_id")
        if kwargs["status"] == "succeeded":
            # Simulate the DB commit succeeding while the client sees a connection error.
            raise RuntimeError("commit acknowledgement lost")
        return {"id": publication_id, **kwargs}
    monkeypatch.setattr(publishing, "finish_publish_attempt", finish)

    with pytest.raises(publishing.PublicationPersistenceError):
        _call()

    assert state == {"status": "succeeded", "pin_id": "committed-pin"}


def test_shared_gateway_uses_atomic_pre_reserved_attempt_without_second_reservation(monkeypatch):
    reserved = {
        "blocked": False, "id": 101, "status": "pending", "product_id": 10,
        "content_version_id": 20, "board_id": "board-1", "account_id": "pinterest:account-1",
    }
    monkeypatch.setattr(publishing, "begin_publish_attempt", lambda **kwargs: pytest.fail("attempt was already reserved atomically"))
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (201, {"id": "pin-atomic"}))
    monkeypatch.setattr(publishing, "finish_publish_attempt", lambda publication_id, **kwargs: {
        "id": publication_id, "status": kwargs["status"],
        "pinterest_pin_id": kwargs["pinterest_pin_id"], "http_status": kwargs["http_status"],
    })

    result = publishing.publish_pin_with_ledger(
        product_id=10,
        content_version_id=20,
        board_id="board-1",
        account_id="pinterest:account-1",
        access_token="vault-token",
        payload=_payload(),
        reserved_attempt=reserved,
    )

    assert result["pin_id"] == "pin-atomic"
    assert result["publication_id"] == 101
