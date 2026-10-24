from fastapi.testclient import TestClient

from app.main import app, settings

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_does_not_expose_secrets():
    response = client.get("/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "database_configured" in body
    assert "pinterest_configured" in body
    assert "image_generation_configured" in body
    assert "llm_configured" in body
    assert "access_token" not in str(body).lower()


def test_product_validate_preserves_affiliate_url():
    affiliate_url = "https://example.com/item?tag=abc-20&campaign=kitchen"
    response = client.post(
        "/products/validate",
        json={
            "product_name": "Wooden spice rack",
            "product_details": "Wall-mounted rack with six jars",
            "image_url": "https://example.com/spice-rack.jpg",
            "affiliate_url": affiliate_url,
        },
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["affiliate_url"] == affiliate_url


def test_product_validate_rejects_blank_name():
    response = client.post(
        "/products/validate",
        json={
            "product_name": "   ",
            "product_details": "Product details",
            "image_url": "https://example.com/product.jpg",
            "affiliate_url": "https://example.com/?tag=abc",
        },
    )
    assert response.status_code == 422


def test_product_create_reports_missing_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    response = client.post(
        "/products",
        json={
            "product_name": "Linen napkins",
            "product_details": "Set of four natural linen napkins",
            "image_url": "https://example.com/napkins.jpg",
            "affiliate_url": "https://example.com/?tag=affiliate-1",
        },
    )
    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.json()["detail"]


def test_product_not_found_when_database_mock_returns_none(monkeypatch):
    from app import database

    monkeypatch.setattr(database, "get_product", lambda product_id: None)
    monkeypatch.setattr(settings, "database_url", "postgresql://example.invalid/test")
    response = client.get("/products/12345")
    assert response.status_code == 404


def test_publish_is_not_faked():
    response = client.post("/publish")
    assert response.status_code == 501
    assert "No Pin was published" in response.json()["detail"]


def test_learning_is_not_faked():
    response = client.post("/learning-loop")
    assert response.status_code == 501
    assert "no model was trained" in response.json()["detail"]
