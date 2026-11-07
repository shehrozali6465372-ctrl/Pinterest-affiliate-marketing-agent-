from fastapi.testclient import TestClient

from app.main import app


def test_personal_browser_integration_routes_are_not_exposed():
    client = TestClient(app)
    assert client.post("/product-research", json={}).status_code == 404
    assert client.post("/amazon-affiliate-url", json={}).status_code == 404
