import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.content_generation import (
    AFFILIATE_DISCLOSURE,
    GeneratedContent,
    generate_pin_content,
)
from app.main import app
from app.pinterest import PinterestPublishError, publish_image_pin

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


def test_deepseek_client_uses_flash_model_and_image_and_adds_disclosure(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "pin_idea": "Style the rack on an organized counter.",
                            "title": "Organized Spice Rack",
                            "description": "A tidy way to arrange everyday spices.",
                            "alt_text": "Wooden rack holding spice jars on a kitchen wall.",
                        })
                    }
                }]
            }

    class FakeClient:
        def __init__(self, timeout):
            calls["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.update(endpoint=endpoint, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)
    content, model = generate_pin_content(
        product_name=VALID_PRODUCT["product_name"],
        product_details=VALID_PRODUCT["product_details"],
        image_url=VALID_PRODUCT["image_url"],
    )
    assert model == "deepseek-flash"
    assert calls["endpoint"] == "https://api.deepseek.com/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer unit-test-secret"
    assert calls["payload"]["messages"][1]["content"][1]["image_url"]["url"] == VALID_PRODUCT["image_url"]
    assert AFFILIATE_DISCLOSURE in content.description


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


def test_content_history_returns_saved_versions(monkeypatch):
    from app import database

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(database, "get_product", lambda product_id: {"id": product_id})
    monkeypatch.setattr(database, "list_content_versions", lambda product_id: [
        {
            "id": 22, "product_id": product_id, "version_number": 2,
            "provider": "deepseek", "model_id": "deepseek-flash",
            "prompt_version": "pin-content-v1", "pin_idea": "A kitchen pin",
            "title": "Tidy Kitchen", "description": AFFILIATE_DISCLOSURE,
            "alt_text": "A spice rack", "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    ])
    response = client.get("/products/5/content")
    assert response.status_code == 200
    assert response.json()["versions"][0]["version_number"] == 2


def test_pinterest_client_uses_real_v5_contract_and_preserves_affiliate_url(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", "unit-test-token")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    affiliate_url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen"
    calls = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "pin-123", "board_id": "board-7", "created_at": "2026-10-24T00:00:00Z"}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.update(endpoint=endpoint, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    result = publish_image_pin(
        board_id="board-7",
        title="A Tidy Kitchen",
        description=AFFILIATE_DISCLOSURE,
        alt_text="Wooden spice rack fixed to a kitchen wall.",
        image_url=VALID_PRODUCT["image_url"],
        affiliate_url=affiliate_url,
    )
    assert calls["endpoint"] == "https://api.pinterest.com/v5/pins"
    assert calls["headers"]["Authorization"] == "Bearer unit-test-token"
    assert calls["payload"]["media_source"]["url"] == VALID_PRODUCT["image_url"]
    assert calls["payload"]["link"] == affiliate_url
    assert result["pin_id"] == "pin-123"


def test_pinterest_client_marks_5xx_as_uncertain(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", "unit-test-token")

    class FakeResponse:
        status_code = 500

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    try:
        publish_image_pin(
            board_id="board-7", title="Title", description="Description",
            alt_text="Alt text", image_url=VALID_PRODUCT["image_url"],
            affiliate_url=VALID_PRODUCT["affiliate_url"],
        )
    except PinterestPublishError as exc:
        assert exc.outcome_uncertain is True
        assert exc.http_status == 500
    else:
        raise AssertionError("Expected PinterestPublishError")


def test_publish_route_needs_real_credentials(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", None)
    monkeypatch.setattr(settings, "pinterest_board_id", None)
    response = client.post("/products/5/content/12/publish")
    assert response.status_code == 503
    assert "must be configured" in response.json()["detail"]


def test_publish_route_persists_confirmed_pin_id(monkeypatch):
    from app import database
    import app.main as main_module

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_access_token", "test-token")
    monkeypatch.setattr(settings, "pinterest_board_id", "board-7")
    product = {"id": 5, **VALID_PRODUCT}
    content = {
        "id": 12, "product_id": 5, "title": "Kitchen Spice Rack",
        "description": AFFILIATE_DISCLOSURE, "alt_text": "A wooden spice rack.",
    }
    attempt = {"blocked": False, "id": 44, "status": "pending"}
    monkeypatch.setattr(database, "get_product", lambda product_id: product)
    monkeypatch.setattr(database, "get_content_version", lambda product_id, version_id: content)
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: attempt)
    monkeypatch.setattr(
        main_module,
        "publish_image_pin",
        lambda **kwargs: {
            "pin_id": "verified-pin-id", "http_status": 201,
            "metadata": {"id": "verified-pin-id", "board_id": "board-7"},
        },
    )
    monkeypatch.setattr(
        database,
        "finish_publish_attempt",
        lambda publication_id, **kwargs: {
            "id": publication_id,
            "status": kwargs["status"],
            "pinterest_pin_id": kwargs["pinterest_pin_id"],
            "http_status": kwargs["http_status"],
        },
    )
    response = client.post("/publish", json={"product_id": 5, "content_version_id": 12})
    assert response.status_code == 200
    assert response.json()["published"] is True
    assert response.json()["pin_id"] == "verified-pin-id"


def test_publish_route_does_not_duplicate_successful_pin(monkeypatch):
    from app import database
    import app.main as main_module

    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_access_token", "test-token")
    monkeypatch.setattr(settings, "pinterest_board_id", "board-7")
    monkeypatch.setattr(database, "get_product", lambda product_id: {"id": product_id})
    monkeypatch.setattr(database, "get_content_version", lambda product_id, version_id: {"id": version_id})
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: {
        "blocked": True, "id": 44, "status": "succeeded", "pinterest_pin_id": "previous-pin-id"
    })
    def must_not_publish(**kwargs):
        raise AssertionError("duplicate Pinterest call should be blocked")
    monkeypatch.setattr(main_module, "publish_image_pin", must_not_publish)
    response = client.post("/publish", json={"product_id": 5, "content_version_id": 12})
    assert response.status_code == 200
    assert response.json()["already_published"] is True
    assert response.json()["pin_id"] == "previous-pin-id"


def test_publish_is_not_faked():
    response = client.post("/publish")
    assert response.status_code == 422


def test_learning_is_not_faked():
    response = client.post("/learning-loop")
    assert response.status_code == 501
    assert "no model was trained" in response.json()["detail"]
