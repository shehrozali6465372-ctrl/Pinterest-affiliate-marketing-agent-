import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.content_generation import (
    AFFILIATE_DISCLOSURE,
    GeneratedContent,
    generate_pin_content,
)
from app.main import app


def _stub_generation_reservation(monkeypatch, workflow):
    monkeypatch.setattr(workflow, "reserve_workflow_generation", lambda **kwargs: {
        "acquired": True, "status": "generating", "image_data_url": None,
        "image_model": None, "generated_content": None, "content_model": None,
    })
    monkeypatch.setattr(workflow, "save_workflow_generation_image", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "save_workflow_generation_content", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "complete_workflow_generation", lambda **kwargs: None)

class AuthenticatedTestClient(TestClient):
    """Attach the configured test key to ordinary endpoint tests by default."""
    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if settings.app_api_key and "X-API-Key" not in headers:
            headers["X-API-Key"] = settings.app_api_key
        kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


client = AuthenticatedTestClient(app)
unauthenticated_client = TestClient(app)


@pytest.fixture(autouse=True)
def configure_test_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-suite-api-key")


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
    assert "pinterest_legacy_direct_configured" in body
    assert "pinterest_account_workflow_configured" in body
    assert "pinterest_token_encryption_key_valid" in body
    assert "pinterest_credential_ingest_configured" in body
    assert "image_generation_configured" in body
    assert "llm_configured" in body
    assert "access_token" not in str(body).lower()


def test_readiness_distinguishes_legacy_and_account_workflow(monkeypatch):
    # Even configured legacy static values must never make the retired path appear ready.
    monkeypatch.setattr(settings, "pinterest_access_token", "legacy-test-token")
    monkeypatch.setattr(settings, "pinterest_board_id", "legacy-test-board")
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "configured-ingest-key")

    body = client.get("/readiness").json()

    assert body["pinterest_configured"] is False
    assert body["pinterest_legacy_direct_configured"] is False
    assert body["pinterest_legacy_direct_publishing_enabled"] is False
    assert body["pinterest_account_workflow_configured"] is True
    assert body["pinterest_token_encryption_key_valid"] is True
    assert body["pinterest_credential_ingest_configured"] is True
    assert "account connection" in body["note"]


def test_readiness_account_publish_does_not_require_ingest_key(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", None)

    body = client.get("/readiness").json()

    assert body["pinterest_account_workflow_configured"] is True
    assert body["pinterest_token_encryption_key_valid"] is True
    assert body["pinterest_credential_ingest_configured"] is False


def test_readiness_account_publish_requires_database_and_encryption(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", None)
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "configured-ingest-key")

    body = client.get("/readiness").json()

    assert body["pinterest_account_workflow_configured"] is False
    assert body["pinterest_token_encryption_key_valid"] is False
    assert body["pinterest_credential_ingest_configured"] is True


def test_operational_routes_fail_closed_when_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)
    assert client.get("/health").status_code == 200
    for response in (
        client.get("/readiness"),
        client.post("/products/validate", json=VALID_PRODUCT),
        client.post("/products", json=VALID_PRODUCT),
        client.get("/products/1"),
    ):
        assert response.status_code == 503
        assert response.json()["detail"] == "API authentication is not configured."


def test_operational_routes_require_valid_api_key_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    assert client.get("/health").status_code == 200
    assert unauthenticated_client.get("/readiness").status_code == 401
    assert unauthenticated_client.post("/products/validate", json=VALID_PRODUCT).status_code == 401
    assert client.post(
        "/products/validate",
        json=VALID_PRODUCT,
        headers={"X-API-Key": "private-test-api-key"},
    ).status_code == 200


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


def test_deepseek_client_uses_image_and_adds_disclosure(monkeypatch):
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
    message_content = calls["payload"]["messages"][1]["content"]
    assert isinstance(message_content, list)
    assert message_content[0]["type"] == "text"
    assert "visible image content" in message_content[0]["text"]
    assert message_content[1]["type"] == "image_url"
    assert message_content[1]["image_url"]["url"] == VALID_PRODUCT["image_url"]
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



def test_publish_routes_fail_closed_without_configured_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)
    payload = {"product_id": 5, "content_version_id": 12}

    direct_route = client.post("/products/5/content/12/publish")
    shorthand_route = client.post("/publish", json=payload)

    assert direct_route.status_code == 503
    assert shorthand_route.status_code == 503
    assert "authentication is not configured" in direct_route.json()["detail"]
    assert "authentication is not configured" in shorthand_route.json()["detail"]


def test_workflow_route_uses_canonical_fail_closed_api_auth(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)
    response = unauthenticated_client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Test product",
            "product_details": "Test details",
            "affiliate_url": "https://example.com/item",
            "account_id": "pinterest:test-account",
        },
        headers={"Idempotency-Key": "workflow-auth-test-123"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured."


def test_legacy_publish_routes_are_retired_and_never_call_gateway(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    import app.main as main_module

    def forbidden_gateway_call(**kwargs):
        raise AssertionError("legacy route must not reach the publishing gateway")

    monkeypatch.setattr(main_module, "publish_pin", forbidden_gateway_call)
    headers = {"X-API-Key": "private-test-api-key"}
    direct = client.post("/products/5/content/12/publish", headers=headers)
    shorthand = client.post("/publish", json={"product_id": 5, "content_version_id": 12}, headers=headers)

    assert direct.status_code == 410
    assert shorthand.status_code == 410
    assert "Legacy publishing is disabled" in direct.json()["detail"]
    assert "encrypted-credential" in shorthand.json()["detail"]


def test_publish_is_not_faked(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    response = client.post("/publish", headers={"X-API-Key": "private-test-api-key"})
    assert response.status_code == 422


def test_learning_is_not_faked():
    response = client.post("/learning-loop")
    assert response.status_code == 501
    assert "no model was trained" in response.json()["detail"]



def test_end_to_end_publish_requires_idempotency_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    payload = {
        "product_name": "Copco 3-Tier Spice Rack Organizer",
        "product_details": "Three-tier spice rack organizer.",
        "affiliate_url": "https://example.com/affiliate",
        "account_id": "pinterest:test-account",
    }
    headers = {"X-API-Key": "private-test-api-key"}
    missing_key = client.post("/workflow/publish-product", json=payload, headers=headers)
    assert missing_key.status_code == 422

    short_key = client.post(
        "/workflow/publish-product",
        json=payload,
        headers={**headers, "Idempotency-Key": "short"},
    )
    assert short_key.status_code == 422


def test_end_to_end_publish_rejects_reused_idempotency_key(monkeypatch):
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(
        workflow,
        "get_product_by_idempotency_key",
        lambda key: {"id": 123, "product_name": "Previously accepted"},
    )
    payload = {
        "product_name": "Copco 3-Tier Spice Rack Organizer",
        "product_details": "Three-tier spice rack organizer.",
        "affiliate_url": "https://example.com/affiliate",
        "account_id": "pinterest:test-account",
    }
    response = client.post(
        "/workflow/publish-product",
        json=payload,
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-12345",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_reused"



def test_end_to_end_publish_checks_pinterest_before_generating_image(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})

    def reject_token(*args, **kwargs):
        raise HTTPException(status_code=401, detail="invalid token")

    def should_not_generate_image(**kwargs):
        raise AssertionError("image generation must not run for an invalid Pinterest token")

    monkeypatch.setattr(workflow, "_pinterest_request", reject_token)
    monkeypatch.setattr(workflow, "generate_pin_image", should_not_generate_image)
    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-12345",
        },
    )
    assert response.status_code == 401
    assert "Stored Pinterest credential could not be verified" in response.json()["detail"]



def test_end_to_end_content_generation_failure_does_not_consume_idempotency_key(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow
    from app.content_generation import ContentGenerationError

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        200, {"id": "test-account"} if path == "/user_account" else {
            "items": [{"id": "board-test", "name": "Modern Living Hub | Kitchen & Home Organization"}]
        }
    ))
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/pin.png",
        "model": "test-image-model",
    })

    def fail_generation(**kwargs):
        raise ContentGenerationError("provider temporarily unavailable")

    persistence_calls = []
    monkeypatch.setattr(workflow, "generate_pin_content", fail_generation)
    monkeypatch.setattr(
        workflow, "create_product_with_content_version",
        lambda **kwargs: persistence_calls.append(kwargs),
    )

    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-content-fail",
        },
    )
    assert response.status_code == 503
    assert "saved image will be reused" in response.json()["detail"]
    assert persistence_calls == []




def test_end_to_end_board_failure_does_not_consume_idempotency_key_or_call_providers(monkeypatch):
    from fastapi import HTTPException
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})

    def pinterest_request(method, path, token, *, body=None):
        if method == "GET" and path == "/user_account":
            return 200, {"id": "test-account"}
        if method == "GET" and path == "/boards?page_size=100":
            raise HTTPException(status_code=502, detail="Pinterest unavailable")
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    provider_calls = []
    persistence_calls = []
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: provider_calls.append("image"))
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: provider_calls.append("content"))
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: persistence_calls.append(kwargs))

    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-board-fail",
        },
    )
    assert response.status_code == 502
    assert provider_calls == []
    assert persistence_calls == []


def test_end_to_end_workflow_uses_atomic_persistence_and_records_real_pin_id(monkeypatch):
    from types import SimpleNamespace
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/pin.png",
        "model": "test-image-model",
    })
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: (
        SimpleNamespace(
            pin_idea="Organized kitchen shelf",
            title="Kitchen Spice Rack Organization",
            description="Organize spices. Affiliate disclosure: This post contains affiliate links; I may earn a commission at no extra cost to you.",
            alt_text="A spice rack organizer.",
        ),
        "deepseek-test-model",
    ))
    persistence = []
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        persistence.append(kwargs) or (
            {"id": 101, "product_name": kwargs["product_name"]},
            {"id": 202, "product_id": 101, "title": kwargs.get("title", "test title"), "description": kwargs.get("description", "test description"), "alt_text": kwargs.get("alt_text", "test alt"), "pin_idea": kwargs.get("pin_idea", "test idea")},
        )
    ))
    monkeypatch.setattr(workflow, "begin_publish_attempt", lambda **kwargs: {
        "blocked": False, "id": 303, "status": "pending",
    })
    monkeypatch.setattr(workflow, "publish_pin", lambda **kwargs: {
        "published": True, "already_published": False, "pin_id": "pin-505",
        "board_id": kwargs["board_id"], "product_id": kwargs["product_id"],
        "content_version_id": kwargs["content_version_id"], "http_status": 201,
    })

    def pinterest_request(method, path, token, *, body=None):
        if method == "GET" and path == "/user_account":
            return 200, {"id": "test-account"}
        if method == "GET" and path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-404", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        if method == "POST" and path == "/pins":
            assert body["link"] == "https://example.com/affiliate"
            return 201, {"id": "pin-505", "created_at": "2026-10-25T00:00:00Z"}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "request-key-success-123",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["pin_id"] == "pin-505"
    assert response.json()["published"] is True
    assert len(persistence) == 1
    assert persistence[0]["idempotency_key"] == "request-key-success-123"


def test_live_diagnostics_requires_api_key_and_never_runs_without_auth(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(
        diagnostics,
        "run_live_diagnostics",
        lambda payload: {"ok": True, "side_effects": {"pinterest_pin_created": False}},
    )
    response = unauthenticated_client.post("/diagnostics/run", json={"account_id": "pinterest:test-account"})
    assert response.status_code == 401


def test_live_diagnostics_runs_read_only_pinterest_and_reports_side_effect_guard(monkeypatch):
    from types import SimpleNamespace
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(settings, "llm_api_key", "test-llm-key")
    monkeypatch.setattr(diagnostics, "_require_api_key", lambda: None)

    class FakeConnection:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def execute(self, query):
            assert query == "SELECT 1"
            return SimpleNamespace(fetchone=lambda: (1,))

    monkeypatch.setattr("app.database.connection", lambda: FakeConnection())
    monkeypatch.setattr(
        "app.credential_vault.get_pinterest_credential",
        lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"},
    )

    class FakeResponse:
        is_success = True
        status_code = 200

    class FakeHttpClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def get(self, url, *, headers):
            assert url.endswith("/user_account")
            assert "Authorization" in headers
            return FakeResponse()

    monkeypatch.setattr(diagnostics.httpx, "Client", FakeHttpClient)
    monkeypatch.setattr(
        "app.media_generation.generate_pin_image",
        lambda **kwargs: {"image_url": "data:image/png;base64,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "model": "test-image-model"},
    )
    monkeypatch.setattr(
        "app.content_generation.generate_pin_content",
        lambda **kwargs: (
            SimpleNamespace(title="Test title", description="Test description", alt_text="Test alt text"),
            "test-deepseek-model",
        ),
    )

    result = diagnostics.run_live_diagnostics(diagnostics.DiagnosticRunInput(account_id="pinterest:test-account"))
    assert result["ok"] is True
    assert result["checks"]["database"]["ok"] is True
    assert result["checks"]["pinterest"]["ok"] is True
    assert result["checks"]["cloudflare_image_generation"]["ok"] is True
    assert result["checks"]["deepseek_multimodal_generation"]["ok"] is True
    assert result["side_effects"]["pinterest_pin_created"] is False
    assert result["side_effects"]["pinterest_board_created"] is False
    assert result["side_effects"]["product_persisted"] is False
    assert result["secrets_returned"] is False


def test_live_diagnostics_does_not_call_image_generator_if_db_or_pinterest_fails(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(settings, "llm_api_key", "test-llm-key")
    monkeypatch.setattr(diagnostics, "_require_api_key", lambda: None)

    class BrokenConnection:
        def __enter__(self):
            raise RuntimeError("database down")
        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("app.database.connection", lambda: BrokenConnection())
    monkeypatch.setattr(
        "app.credential_vault.get_pinterest_credential",
        lambda account_id: (_ for _ in ()).throw(LookupError("not connected")),
    )
    called = []
    monkeypatch.setattr(
        "app.media_generation.generate_pin_image",
        lambda **kwargs: called.append(True),
    )

    result = diagnostics.run_live_diagnostics(diagnostics.DiagnosticRunInput(account_id="pinterest:missing"))
    assert result["ok"] is False
    assert called == []
    assert result["side_effects"]["cloudflare_test_image_uploaded"] is False




def test_pinterest_read_only_diagnostic_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    response = unauthenticated_client.get("/diagnostics/pinterest")
    assert response.status_code == 401


def test_pinterest_read_only_diagnostic_checks_account_without_generation(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(
        "app.credential_vault.get_pinterest_credential",
        lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"},
    )

    class FakeResponse:
        is_success = True
        status_code = 200

    calls = []

    class FakeHttpClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return False
        def get(self, url, *, headers):
            calls.append((url, headers))
            return FakeResponse()

    monkeypatch.setattr(diagnostics.httpx, "Client", FakeHttpClient)
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:test-account",
        headers={"X-API-Key": "private-test-api-key"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["http_status"] == 200
    assert body["side_effects"]["pinterest_pin_created"] is False
    assert body["side_effects"]["ai_generation_called"] is False
    assert body["side_effects"]["image_generation_called"] is False
    assert len(calls) == 1
    assert calls[0][0] == "https://api.pinterest.com/v5/user_account"
    assert calls[0][1]["Authorization"] == "Bearer test-token"


def test_pinterest_read_only_diagnostic_handles_missing_credential(monkeypatch):
    from app import diagnostics

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(
        "app.credential_vault.get_pinterest_credential",
        lambda account_id: (_ for _ in ()).throw(LookupError("no credential")),
    )
    response = client.get(
        "/diagnostics/pinterest?account_id=pinterest:missing",
        headers={"X-API-Key": "private-test-api-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "credential_not_connected"



def test_deepseek_invalid_json_retries_once_and_returns_real_valid_content(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    calls = []

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def __init__(self, content):
            self._content = content

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"finish_reason": "stop", "message": {"content": self._content}}]}

    responses = [
        FakeResponse('{"pin_idea":"truncated'),
        FakeResponse(json.dumps({
            "pin_idea": "Arrange the spice rack beside a clear prep area.",
            "title": "Organized Spice Rack",
            "description": "A practical kitchen organization idea.",
            "alt_text": "A wooden spice rack holding jars on a kitchen wall.",
        })),
    ]

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.append(endpoint)
            return responses.pop(0)

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)
    content, model = generate_pin_content(
        product_name=VALID_PRODUCT["product_name"],
        product_details=VALID_PRODUCT["product_details"],
        image_url=VALID_PRODUCT["image_url"],
    )

    assert len(calls) == 2
    assert model == "deepseek-flash"
    assert content.title == "Organized Spice Rack"
    assert AFFILIATE_DISCLOSURE in content.description
def test_end_to_end_board_failure_allows_same_idempotency_key_retry(monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})

    provider_calls = []
    persistence = []
    board_lookups = []
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: (
        provider_calls.append("image") or {"image_url": "https://cdn.example.com/pin.png", "model": "test-image-model"}
    ))
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: (
        provider_calls.append("content") or (
            SimpleNamespace(
                pin_idea="Organized kitchen shelf", title="Kitchen Spice Rack Organization",
                description="Affiliate disclosure: This post contains affiliate links.",
                alt_text="A spice rack organizer.",
            ),
            "deepseek-test-model",
        )
    ))
    monkeypatch.setattr(
        workflow, "create_product_with_content_version",
        lambda **kwargs: persistence.append(kwargs) or (
            {"id": 101, "product_name": kwargs["product_name"]},
            {"id": 202, "product_id": 101, "title": kwargs.get("title", "test title"), "description": kwargs.get("description", "test description"), "alt_text": kwargs.get("alt_text", "test alt"), "pin_idea": kwargs.get("pin_idea", "test idea")},
        ),
    )
    monkeypatch.setattr(workflow, "publish_pin", lambda **kwargs: {
        "published": True, "already_published": False,
        "pin_id": "pin-created-after-retry", "board_id": kwargs["board_id"],
        "product_id": kwargs["product_id"], "content_version_id": kwargs["content_version_id"],
        "http_status": 201,
    })

    def pinterest_request(method, path, token, *, body=None):
        if path == "/user_account":
            return 200, {"id": "test-account"}
        if path == "/boards?page_size=100":
            board_lookups.append(path)
            if len(board_lookups) == 1:
                raise HTTPException(status_code=502, detail="board lookup failed")
            return 200, {"items": [{"id": "board-7", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        if path == "/pins":
            return 201, {"id": "pin-created-after-retry", "created_at": "2026-10-27T00:00:00Z"}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    payload = {
        "product_name": "Copco 3-Tier Spice Rack Organizer",
        "product_details": "Three-tier spice rack organizer.",
        "affiliate_url": "https://example.com/affiliate?tag=home-20",
        "account_id": "pinterest:test-account",
    }
    headers = {
        "X-API-Key": "private-test-api-key",
        "Idempotency-Key": "retry-board-failure-123",
    }

    first = client.post("/workflow/publish-product", json=payload, headers=headers)
    assert first.status_code == 502
    assert persistence == []
    assert provider_calls == []
    assert len(board_lookups) == 1

    # The exact same idempotency key remains safe after a pre-persistence board failure.
    retry = client.post("/workflow/publish-product", json=payload, headers=headers)
    assert retry.status_code == 200, retry.text
    body = retry.json()
    assert body["published"] is True
    assert body["pin_id"] == "pin-created-after-retry"
    assert body["affiliate_url"] == payload["affiliate_url"]
    assert len(board_lookups) == 2
    assert len(persistence) == 1
    assert provider_calls == ["image", "content"]


def test_end_to_end_missing_pin_id_is_marked_uncertain(monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/pin.png", "model": "test-image-model",
    })
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: (
        SimpleNamespace(
            pin_idea="Organized kitchen shelf", title="Kitchen Spice Rack Organization",
            description="Affiliate disclosure: This post contains affiliate links.",
            alt_text="A spice rack organizer.",
        ),
        "deepseek-test-model",
    ))
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        {"id": 101, "product_name": kwargs["product_name"]},
        {"id": 202, "product_id": 101, "title": kwargs.get("title", "test title"), "description": kwargs.get("description", "test description"), "alt_text": kwargs.get("alt_text", "test alt"), "pin_idea": kwargs.get("pin_idea", "test idea")},
    ))
    monkeypatch.setattr(workflow, "begin_publish_attempt", lambda **kwargs: {
        "blocked": False, "id": 303, "status": "pending",
    })
    finishes = []
    def uncertain_gateway(**kwargs):
        raise HTTPException(status_code=502, detail="Pinterest returned no Pin ID; outcome is uncertain. Verify the board before retrying.")
    monkeypatch.setattr(workflow, "publish_pin", uncertain_gateway)

    def pinterest_request(method, path, token, *, body=None):
        if path == "/user_account":
            return 200, {"id": "test-account"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-7", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        if path == "/pins":
            return 201, {"created_at": "2026-10-26T00:00:00Z"}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    response = client.post(
        "/workflow/publish-product",
        json={
            "product_name": "Copco 3-Tier Spice Rack Organizer",
            "product_details": "Three-tier spice rack organizer.",
            "affiliate_url": "https://example.com/affiliate",
            "account_id": "pinterest:test-account",
        },
        headers={
            "X-API-Key": "private-test-api-key",
            "Idempotency-Key": "missing-pin-id-uncertain-123",
        },
    )

    assert response.status_code == 502
    assert "outcome is uncertain" in response.json()["detail"]



def test_readiness_rejects_present_but_invalid_encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", "present-but-not-valid-base64")

    body = client.get("/readiness").json()

    assert body["pinterest_token_encryption_key_valid"] is False
    assert body["pinterest_account_workflow_configured"] is False
    assert "present-but-not-valid-base64" not in str(body)


def test_analytics_integration_route_requires_service_credential(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "private-ingest-test")
    body = {"account_id": "pinterest:account-a"}
    assert client.post("/integrations/pinterest/analytics/run", json=body).status_code == 401



def test_workflow_rejects_stored_account_identity_mismatch_before_board_or_generation(monkeypatch):
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "pinterest_user_id": "different-user",
    })
    calls = []
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        calls.append((method, path)) or (200, {"id": "test-account"})
    ))
    provider_calls = []
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: provider_calls.append("image"))
    response = client.post(
        "/workflow/publish-product",
        json={"product_name": "Test product", "product_details": "Details",
              "affiliate_url": "https://example.com/item", "account_id": "pinterest:test-account"},
        headers={"X-API-Key": "private-test-api-key", "Idempotency-Key": "identity-mismatch-123"},
    )
    assert response.status_code == 409
    assert calls == [("GET", "/user_account")]
    assert provider_calls == []


def test_workflow_does_not_create_missing_pinterest_board(monkeypatch):
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    _stub_generation_reservation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "pinterest_user_id": "test-account",
    })
    calls = []
    def pinterest_request(method, path, token, **kwargs):
        calls.append((method, path))
        if path == "/user_account":
            return 200, {"id": "test-account"}
        if path == "/boards?page_size=100":
            return 200, {"items": []}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")
    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    provider_calls = []
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: provider_calls.append("image"))
    response = client.post(
        "/workflow/publish-product",
        json={"product_name": "Test product", "product_details": "Details",
              "affiliate_url": "https://example.com/item", "account_id": "pinterest:test-account"},
        headers={"X-API-Key": "private-test-api-key", "Idempotency-Key": "missing-board-12345"},
    )
    assert response.status_code == 422
    assert "does not create boards" in response.json()["detail"]
    assert calls == [("GET", "/user_account"), ("GET", "/boards?page_size=100")]
    assert provider_calls == []
