from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app import model2_learning as learning
from app.model2_repository import Model2NotFoundError


@pytest.fixture(autouse=True)
def configured_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "model2-learning-test-key")


@pytest.fixture
def client():
    return TestClient(app)


def headers():
    return {"X-API-Key": "model2-learning-test-key"}


def snapshot():
    return {
        "snapshot_id": 42,
        "account_id": "pinterest:123456789",
        "niche_id": 7,
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 30),
        "metrics": {
            "impression": 100,
            "save": None,
            "pin_click": 5,
            "outbound_click": 10,
        },
        "sample_size": 2,
        "source_snapshot_count": 2,
        "learning_status": "descriptive_only",
        "created": True,
    }


def test_projection_api_fails_closed_without_api_key(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        learning,
        "create_learning_snapshot",
        lambda **kwargs: called.append(kwargs),
    )

    response = client.post(
        "/model2/learning/snapshots",
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
        },
    )

    assert response.status_code == 401
    assert called == []


def test_projection_api_returns_503_if_auth_is_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)

    response = client.get(
        "/model2/learning/accounts/pinterest%3A123456789/niches/7/snapshots"
    )

    assert response.status_code == 503


def test_create_projection_endpoint_returns_explicit_snapshot_fields(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        learning,
        "create_learning_snapshot",
        lambda **kwargs: calls.append(kwargs) or snapshot(),
    )

    response = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
        },
    )

    assert response.status_code == 200
    assert response.json()["snapshot_id"] == 42
    assert response.json()["metrics"]["save"] is None
    assert "access_token" not in response.text
    assert calls == [{
        "account_id": "pinterest:123456789",
        "niche_id": 7,
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 30),
    }]


def test_create_projection_returns_insufficient_data_without_fabricating_zeroes(client, monkeypatch):
    empty = {
        **snapshot(),
        "snapshot_id": None,
        "metrics": {
            "impression": None,
            "save": None,
            "pin_click": None,
            "outbound_click": None,
        },
        "sample_size": 0,
        "source_snapshot_count": 0,
        "learning_status": "insufficient_data",
        "created": False,
    }
    monkeypatch.setattr(learning, "create_learning_snapshot", lambda **kwargs: empty)

    response = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
        },
    )

    assert response.status_code == 200
    assert response.json()["learning_status"] == "insufficient_data"
    assert response.json()["metrics"] == {
        "impression": None,
        "save": None,
        "pin_click": None,
        "outbound_click": None,
    }


def test_create_projection_maps_missing_assignment_to_404(client, monkeypatch):
    monkeypatch.setattr(
        learning,
        "create_learning_snapshot",
        lambda **kwargs: (_ for _ in ()).throw(
            Model2NotFoundError("Account niche assignment does not exist")
        ),
    )

    response = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
        },
    )

    assert response.status_code == 404


def test_projection_api_rejects_invalid_period_and_unknown_fields(client):
    reversed_period = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-30",
            "period_end": "2026-10-01",
        },
    )
    assert reversed_period.status_code == 422

    unknown_field = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
            "owner_id": "not-accepted",
        },
    )
    assert unknown_field.status_code == 422


def test_list_projection_api_is_account_and_niche_scoped(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        learning,
        "list_learning_snapshots",
        lambda **kwargs: calls.append(kwargs) or [snapshot()],
    )

    response = client.get(
        "/model2/learning/accounts/pinterest%3A123456789/niches/7/snapshots?limit=10",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()[0]["snapshot_id"] == 42
    assert calls == [{
        "account_id": "pinterest:123456789",
        "niche_id": 7,
        "limit": 10,
    }]


def test_projection_creation_does_not_call_publisher_or_provider(client, monkeypatch):
    from app import publishing_gateway

    calls = []
    monkeypatch.setattr(publishing_gateway, "publish_pin", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(learning, "create_learning_snapshot", lambda **kwargs: snapshot())

    response = client.post(
        "/model2/learning/snapshots",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "period_start": "2026-10-01",
            "period_end": "2026-10-30",
        },
    )

    assert response.status_code == 200
    assert calls == []


def test_projection_api_does_not_call_publisher(client, monkeypatch):
    from app import publishing_gateway

    calls = []
    monkeypatch.setattr(
        publishing_gateway,
        "publish_pin",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(learning, "list_learning_snapshots", lambda **kwargs: [])

    response = client.get(
        "/model2/learning/accounts/pinterest%3A123456789/niches/7/snapshots",
        headers=headers(),
    )

    assert response.status_code == 200
    assert calls == []
