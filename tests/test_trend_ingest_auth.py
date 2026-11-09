"""Regression tests for canonical fail-closed trusted-Hub authentication."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_trends_ingest_returns_service_unavailable_when_ingest_key_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", None)
    response = TestClient(app).post(
        "/trend-intelligence/run",
        json={"account_id": "pinterest:123456", "regions": ["US"]},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Credential-ingest authentication is not configured."


def test_trends_ingest_rejects_invalid_ingest_key(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-trusted-hub-key")
    response = TestClient(app).post(
        "/trend-intelligence/run",
        headers={"X-Credential-Ingest-Key": "wrong-key"},
        json={"account_id": "pinterest:123456", "regions": ["US"]},
    )
    assert response.status_code == 401


def test_trends_ingest_accepts_valid_key_and_calls_read_only_fetch(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "synthetic-trusted-hub-key")
    from app import trends

    calls = []
    monkeypatch.setattr(
        trends,
        "fetch_trends",
        lambda account_id, regions, limit: calls.append((account_id, regions, limit)) or {"ok": True, "read_only": True},
    )
    response = TestClient(app).post(
        "/trend-intelligence/run",
        headers={"X-Credential-Ingest-Key": "synthetic-trusted-hub-key"},
        json={"account_id": "pinterest:123456", "regions": ["US"]},
    )
    assert response.status_code == 200
    assert response.json()["read_only"] is True
    assert calls == [("pinterest:123456", ["US"], 50)]
