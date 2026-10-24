from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.content_generation import AFFILIATE_DISCLOSURE, GeneratedContent
from app.main import app

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


def test_content_generation_requires_real_credentials(monkeypatch):
    from app import database

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(database, "get_product", lambda product_id: {
        "id": product_id,
        "product_name": VALID_PRODUCT["product_name"],
        "product_details": VALID_PRODUCT["product_details"],
        "image_url": VALID_PRODUCT["image_url"],
        "affiliate_url": VALID_PRODUCT["affiliate_url"],
    })
    response = client.post("/products/1/content")
    assert response.status_code == 503
    assert "LLM_API_KEY is not configured" in response.json()["detail"]


def test_content_generation_saves_real_provider_result(monkeypatch):
    from app import database
    import app.main as main_module

    saved_rows = []
    product = {
        "id": 5,
        "product_name": VALID_PRODUCT["product_name"],
        "product_details": VALID_PRODUCT["product_details"],
        "image_url": VALID_PRODUCT["image_url"],
        "affiliate_url": VALID_PRODUCT["affiliate_url"],
    }

    def save_version(**kwargs):
        saved_rows.append(kwargs)
        return {
            "id": 12,
            "product_id": kwargs["product_id"],
            "version_number": 1,
            **kwargs,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "llm_api_key", "test-only-key")
    monkeypatch.setattr(database, "get_product", lambda product_id: product)
    monkeypatch.setattr(database, "create_content_version", save_version)
    monkeypatch.setattr(
        main_module,
        "generate_pin_content",
        lambda **kwargs: (
            GeneratedContent(
                pin_idea="Show the spice rack beside a neatly arranged kitchen counter.",
                title="A Tidy Kitchen Spice Rack",
                description=AFFILIATE_DISCLOSURE,
                alt_text="A wooden spice rack with jars mounted on a kitchen wall.",
            ),
            "deepseek-flash",
        ),
    )
    response = client.post("/products/5/content")
    assert response.status_code == 200
    assert response.json()["model_id"] == "deepseek-flash"
    assert response.json()["description"] == AFFILIATE_DISCLOSURE
    assert saved_rows[0]["product_id"] == 5
    assert saved_rows[0]["prompt_version"] == "pin-content-v1"


def test_publish_is_not_faked():
    response = client.post("/publish")
    assert response.status_code == 501
    assert "No Pin was published" in response.json()["detail"]


def test_learning_is_not_faked():
    response = client.post("/learning-loop")
    assert response.status_code == 501
    assert "no model was trained" in response.json()["detail"]
