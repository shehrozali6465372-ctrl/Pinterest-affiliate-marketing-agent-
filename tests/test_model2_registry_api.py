from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app import model2_registry as registry
from app.model2_repository import (
    Model2AccountNotConnectedError,
    Model2ConflictError,
    Model2NotFoundError,
)


@pytest.fixture(autouse=True)
def configured_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "model2-api-test-key")


@pytest.fixture
def client():
    return TestClient(app)


def headers():
    return {"X-API-Key": "model2-api-test-key"}


def profile_row(account_id="pinterest:123456789"):
    now = datetime.now(timezone.utc)
    return {
        "account_id": account_id,
        "display_name": "Kitchen Account",
        "status": "active",
        "timezone": "Asia/Karachi",
        "created_at": now,
        "updated_at": now,
    }


def niche_row():
    now = datetime.now(timezone.utc)
    return {
        "id": 7,
        "slug": "home-decor",
        "display_name": "Home Decor",
        "description": "",
        "default_region": "US",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }


def assignment_row(account_id="pinterest:123456789", niche_id=7):
    now = datetime.now(timezone.utc)
    return {
        "account_id": account_id,
        "niche_id": niche_id,
        "is_primary": True,
        "status": "active",
        "settings": {},
        "created_at": now,
        "updated_at": now,
    }


def test_registry_routes_fail_closed_without_api_key(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "list_account_profiles", lambda: called.append(True) or [])

    response = client.get("/model2/accounts")

    assert response.status_code == 401
    assert called == []


def test_registry_routes_return_503_when_api_key_is_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)

    response = client.get("/model2/accounts")

    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured."


def test_registry_routes_reject_invalid_api_key(client):
    response = client.get(
        "/model2/accounts",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_list_accounts_returns_only_explicit_response_fields(client, monkeypatch):
    monkeypatch.setattr(registry, "list_account_profiles", lambda: [profile_row()])

    response = client.get("/model2/accounts", headers=headers())

    assert response.status_code == 200
    assert response.json()[0]["account_id"] == "pinterest:123456789"
    assert "access_token" not in response.text
    assert "ciphertext" not in response.text


def test_get_account_rejects_noncanonical_path_id_before_repository_call(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "get_account_profile", lambda account_id: called.append(account_id))

    response = client.get("/model2/accounts/not-pinterest", headers=headers())

    assert response.status_code == 422
    assert called == []


def test_get_account_returns_404_when_profile_missing(client, monkeypatch):
    monkeypatch.setattr(registry, "get_account_profile", lambda account_id: None)

    response = client.get("/model2/accounts/pinterest%3A123456789", headers=headers())

    assert response.status_code == 404


def test_put_account_requires_path_and_payload_account_to_match(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "save_account_profile", lambda payload: called.append(payload))

    response = client.put(
        "/model2/accounts/pinterest%3A123456789",
        headers=headers(),
        json={
            "account_id": "pinterest:987654321",
            "display_name": "Other account",
            "status": "active",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 422
    assert called == []


def test_put_account_requires_explicit_status_and_timezone(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "save_account_profile", lambda payload: called.append(payload))

    response = client.put(
        "/model2/accounts/pinterest%3A123456789",
        headers=headers(),
        json={"account_id": "pinterest:123456789", "display_name": "Kitchen"},
    )

    assert response.status_code == 422
    assert called == []


def test_put_account_maps_disconnected_credential_to_conflict(client, monkeypatch):
    def reject(payload):
        raise Model2AccountNotConnectedError("Pinterest account must be connected")

    monkeypatch.setattr(registry, "save_account_profile", reject)

    response = client.put(
        "/model2/accounts/pinterest%3A123456789",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "display_name": "Kitchen",
            "status": "active",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 409
    assert "must be connected" in response.json()["detail"]


def test_get_account_niches_checks_profile_and_scopes_repository_call(client, monkeypatch):
    calls = []
    monkeypatch.setattr(registry, "get_account_profile", lambda account_id: profile_row(account_id))
    monkeypatch.setattr(
        registry,
        "list_account_niche_assignments",
        lambda account_id: calls.append(account_id) or [assignment_row(account_id)],
    )

    response = client.get(
        "/model2/accounts/pinterest%3A123456789/niches",
        headers=headers(),
    )

    assert response.status_code == 200
    assert calls == ["pinterest:123456789"]
    assert response.json()[0]["account_id"] == "pinterest:123456789"


def test_get_account_niches_returns_404_for_unknown_profile(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "get_account_profile", lambda account_id: None)
    monkeypatch.setattr(registry, "list_account_niche_assignments", lambda account_id: called.append(account_id))

    response = client.get(
        "/model2/accounts/pinterest%3A123456789/niches",
        headers=headers(),
    )

    assert response.status_code == 404
    assert called == []


def test_put_account_niche_rejects_path_body_mismatch(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "save_account_niche_assignment", lambda payload: called.append(payload))

    response = client.put(
        "/model2/accounts/pinterest%3A123456789/niches/7",
        headers=headers(),
        json={
            "account_id": "pinterest:987654321",
            "niche_id": 7,
            "is_primary": True,
            "status": "active",
        },
    )

    assert response.status_code == 422
    assert called == []


def test_put_account_niche_requires_explicit_primary_and_status(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "save_account_niche_assignment", lambda payload: called.append(payload))

    response = client.put(
        "/model2/accounts/pinterest%3A123456789/niches/7",
        headers=headers(),
        json={"account_id": "pinterest:123456789", "niche_id": 7},
    )

    assert response.status_code == 422
    assert called == []


def test_put_account_niche_maps_state_conflict_to_409(client, monkeypatch):
    monkeypatch.setattr(
        registry,
        "save_account_niche_assignment",
        lambda payload: (_ for _ in ()).throw(Model2ConflictError("Archived niche cannot be activated")),
    )

    response = client.put(
        "/model2/accounts/pinterest%3A123456789/niches/7",
        headers=headers(),
        json={
            "account_id": "pinterest:123456789",
            "niche_id": 7,
            "is_primary": True,
            "status": "active",
        },
    )

    assert response.status_code == 409


def test_get_niches_excludes_archived_by_default(client, monkeypatch):
    calls = []
    monkeypatch.setattr(registry, "list_niches", lambda **kwargs: calls.append(kwargs) or [niche_row()])

    response = client.get("/model2/niches", headers=headers())

    assert response.status_code == 200
    assert calls == [{"include_archived": False}]


def test_post_niche_returns_201_and_maps_duplicate_slug_to_409(client, monkeypatch):
    monkeypatch.setattr(registry, "create_niche", lambda payload: niche_row())
    response = client.post(
        "/model2/niches",
        headers=headers(),
        json={"slug": "home-decor", "display_name": "Home Decor"},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "home-decor"

    monkeypatch.setattr(
        registry,
        "create_niche",
        lambda payload: (_ for _ in ()).throw(Model2ConflictError("A niche with this slug already exists")),
    )
    duplicate = client.post(
        "/model2/niches",
        headers=headers(),
        json={"slug": "home-decor", "display_name": "Home Decor"},
    )
    assert duplicate.status_code == 409


def test_put_niche_requires_explicit_status_and_region(client, monkeypatch):
    called = []
    monkeypatch.setattr(registry, "update_niche", lambda niche_id, payload: called.append(niche_id))

    response = client.put(
        "/model2/niches/7",
        headers=headers(),
        json={"slug": "home-decor", "display_name": "Home Decor"},
    )

    assert response.status_code == 422
    assert called == []


def test_put_niche_maps_missing_row_to_404(client, monkeypatch):
    monkeypatch.setattr(
        registry,
        "update_niche",
        lambda niche_id, payload: (_ for _ in ()).throw(Model2NotFoundError("Niche does not exist")),
    )

    response = client.put(
        "/model2/niches/7",
        headers=headers(),
        json={
            "slug": "home-decor",
            "display_name": "Home Decor",
            "status": "active",
            "default_region": "US",
        },
    )

    assert response.status_code == 404


def test_registry_never_invokes_pinterest_publisher(client, monkeypatch):
    from app import publishing_gateway

    calls = []
    monkeypatch.setattr(publishing_gateway, "publish_pin", lambda **kwargs: calls.append(kwargs))

    monkeypatch.setattr(registry, "list_account_profiles", lambda: [profile_row()])
    response = client.get("/model2/accounts", headers=headers())

    assert response.status_code == 200
    assert calls == []


def test_response_model_fails_closed_if_repository_returns_unapproved_secret_field(monkeypatch):
    secret_marker = 'must-not-leak-test-secret'
    monkeypatch.setattr(
        registry,
        'list_account_profiles',
        lambda: [{**profile_row(), 'access_token': secret_marker}],
    )
    strict_client = TestClient(app, raise_server_exceptions=False)

    response = strict_client.get('/model2/accounts', headers=headers())

    assert response.status_code == 500
    assert secret_marker not in response.text
