from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_dashboard_requires_login(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "dashboard-test-key")
    client = TestClient(app, base_url="https://testserver")
    response = client.get("/dashboard/api/overview")
    assert response.status_code == 401


def test_dashboard_login_sets_secure_http_only_session(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "dashboard-test-key")
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/dashboard/session", json={"api_key": "dashboard-test-key"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie
    assert "agent_dashboard_session=" in cookie


def test_dashboard_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "dashboard-test-key")
    client = TestClient(app, base_url="https://testserver")
    response = client.post("/dashboard/session", json={"api_key": "wrong"})
    assert response.status_code == 401
