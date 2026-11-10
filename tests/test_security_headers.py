"""Security headers are consistently applied to API, docs, and error responses."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


EXPECTED_HEADERS = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


@pytest.mark.parametrize("path", ["/health", "/openapi.json", "/docs", "/missing-route"])
def test_security_headers_are_applied_to_public_api_docs_and_errors(path):
    response = TestClient(app, base_url="https://testserver").get(path)

    assert response.status_code in {200, 404}
    headers = {name.lower(): value for name, value in response.headers.items()}
    for name, value in EXPECTED_HEADERS.items():
        assert headers.get(name) == value


def test_security_headers_are_applied_to_authentication_failures(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-only-api-key")
    response = TestClient(app, base_url="https://testserver").get("/readiness")

    assert response.status_code == 401
    headers = {name.lower(): value for name, value in response.headers.items()}
    for name, value in EXPECTED_HEADERS.items():
        assert headers.get(name) == value


def test_hsts_is_enabled_for_https_forwarded_by_the_render_proxy():
    response = TestClient(app, base_url="http://testserver").get(
        "/health",
        headers={"X-Forwarded-Proto": "https"},
    )

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_hsts_is_not_enabled_for_plain_local_http():
    response = TestClient(app, base_url="http://testserver").get("/health")

    assert response.status_code == 200
    assert "strict-transport-security" not in response.headers
