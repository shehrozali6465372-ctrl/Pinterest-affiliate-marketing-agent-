from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app, settings

client = TestClient(app)

VALID_PRODUCT = {
    "product_name": "Wooden spice rack",
    "product_details": "Wall-mounted rack with six jars",
    "image_url": "https://example.com/spice-rack.jpg",
    "affiliate_url": "https://example.com/item?tag=abc-20&campaign=kitchen",
}


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


def test_product_validate_preserves_affiliate_url_byte_for_byte():
    affiliate_url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen&x=a%2Fb"
    response = client.post(
        "/products/validate",
        json={**VALID_PRODUCT, "affiliate_url": affiliate_url},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["affiliate_url"] == affiliate_url


def test_product_validate_rejects_malformed_affiliate_url():
    response = client.post(
        "/products/validate",
        json={**VALID_PRODUCT, "affiliate_url": "javascript:alert(1)"},
    )
    assert response.status_code == 422


def test_product_validate_rejects_blank_name():
    response = client.post(
        "/products/validate",
        json={**VALID_PRODUCT, "product_name": "   "},
    )
    assert response.status_code == 422


def test_product_create_reports_missing_database(monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    response = client.post("/products", json=VALID_PRODUCT)
    assert response.status_code == 503
    assert "DATABASE_URL is not configured" in response.json()["detail"]


def test_product_create_returns_saved_record_and_preserved_link(monkeypatch):
    from app import database

    affiliate_url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen"
    record = {
        "id": 17,
        "product_name": VALID_PRODUCT["product_name"],
        "product_details": VALID_PRODUCT["product_details"],
        "image_url": VALID_PRODUCT["image_url"],
        "affiliate_url": affiliate_url,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(database, "create_product", lambda **kwargs: record)
    response = client.post("/products", json={**VALID_PRODUCT, "affiliate_url": affiliate_url})
    assert response.status_code == 201
    assert response.json()["id"] == 17
    assert response.json()["affiliate_url"] == affiliate_url


def test_product_not_found_when_database_returns_none(monkeypatch):
    from app import database

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(database, "get_product", lambda product_id: None)
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
