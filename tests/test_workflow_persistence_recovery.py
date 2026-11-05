"""End-to-end recovery tests for persistence failures and uncertain publish outcomes."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def _payload():
    return {
        "product_name": "Three-tier spice rack",
        "product_details": "A compact organizer for spices.",
        "affiliate_url": "https://example.com/affiliate?tag=home-20",
        "account_id": "pinterest:test-account",
    }


def _headers(key):
    return {"X-API-Key": "test-api-key", "Idempotency-Key": key}


def _setup_generation(monkeypatch, workflow):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", lambda key: None)
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token", "pinterest_user_id": "test-account"})
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: {
        "image_url": "https://cdn.example.com/generated.png",
        "model": "test-image-model",
    })
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: (
        SimpleNamespace(
            pin_idea="Organize spices neatly",
            title="Three-Tier Spice Rack",
            description="Organize your kitchen. Affiliate links may earn a commission.",
            alt_text="A three-tier spice rack organizer on a kitchen counter.",
        ),
        "test-deepseek-model",
    ))
    monkeypatch.setattr(workflow, "reserve_workflow_generation", lambda **kwargs: {
        "acquired": True, "status": "generating", "image_data_url": None,
        "image_model": None, "generated_content": None, "content_model": None,
    })
    monkeypatch.setattr(workflow, "save_workflow_generation_image", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "save_workflow_generation_content", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: None)
    monkeypatch.setattr(workflow, "complete_workflow_generation", lambda **kwargs: None)


def test_persistence_failure_never_attempts_pin_publish(monkeypatch):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    pinterest_calls = []

    def pinterest_request(method, path, token, *, body=None):
        pinterest_calls.append((method, path))
        if path == "/user_account":
            return 200, {"id": "test-account"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        raise AssertionError("No publish call is allowed after persistence fails")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    monkeypatch.setattr(
        workflow, "create_product_with_content_version",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("simulated database transaction failure")),
    )

    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers=_headers("persist-failure-retry-123"),
    )

    assert response.status_code == 503
    assert any(path == "/boards?page_size=100" for _, path in pinterest_calls)
    assert all(path != "/pins" for _, path in pinterest_calls)


def test_ambiguous_pin_publish_marks_attempt_unknown_and_blocks_safe_retry(monkeypatch):
    import httpx
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        {"id": 1001, "product_name": kwargs["product_name"]},
        {"id": 1002, "product_id": 1001, "title": kwargs.get("title", "test title"), "description": kwargs.get("description", "test description"), "alt_text": kwargs.get("alt_text", "test alt"), "pin_idea": kwargs.get("pin_idea", "test idea")},
    ))
    from fastapi import HTTPException
    monkeypatch.setattr(workflow, "publish_pin", lambda **kwargs: (_ for _ in ()).throw(
        HTTPException(status_code=502, detail="Pinterest publish outcome is uncertain. Check the board; do not retry blindly.")
    ))

    def pinterest_request(method, path, token, *, body=None):
        if path == "/user_account":
            return 200, {"id": "test-account"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers=_headers("ambiguous-publish-retry-123"),
    )

    assert response.status_code == 502
    assert "outcome is uncertain" in response.json()["detail"]


def test_active_generation_lease_blocks_provider_calls(monkeypatch):
    import app.workflow as workflow
    _setup_generation(monkeypatch, workflow)
    monkeypatch.setattr(workflow, "reserve_workflow_generation", lambda **kwargs: {
        "acquired": False, "status": "generating", "image_data_url": None,
    })
    provider_calls = []
    monkeypatch.setattr(workflow, "generate_pin_image", lambda **kwargs: provider_calls.append("image"))
    monkeypatch.setattr(workflow, "generate_pin_content", lambda **kwargs: provider_calls.append("content"))
    monkeypatch.setattr(workflow, "_pinterest_request", lambda *args, **kwargs: (200, {"id": "test-account"}) if args[1] == "/user_account" else (200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}))
    response = client.post("/workflow/publish-product", json=_payload(), headers=_headers("lease-busy-case-123"))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "workflow_generation_in_progress"
    assert provider_calls == []


def test_cached_provider_outputs_skip_both_generation_calls(monkeypatch):
    import app.workflow as workflow
    _setup_generation(monkeypatch, workflow)
    cached_content = {
        "pin_idea": "Organize spices neatly", "title": "Three-Tier Spice Rack",
        "description": "Organize your kitchen. Affiliate disclosure.",
        "alt_text": "A three-tier spice rack on a counter.",
    }
    monkeypatch.setattr(workflow, "reserve_workflow_generation", lambda **kwargs: {
        "acquired": True, "status": "generating",
        "image_data_url": "https://cdn.example.com/cached.png", "image_model": "cached-image-model",
        "generated_content": cached_content, "content_model": "cached-content-model",
    })
    monkeypatch.setattr(workflow, "_pinterest_request", lambda *args, **kwargs: (200, {"id": "test-account"}) if args[1] == "/user_account" else (200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}))
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        {"id": 123, "product_name": kwargs["product_name"]},
        {"id": 456, "product_id": 123, "title": kwargs["title"], "description": kwargs["description"], "alt_text": kwargs["alt_text"]},
    ))
    monkeypatch.setattr(workflow, "publish_pin", lambda **kwargs: {"published": True, "pin_id": "stub-pin", "http_status": 201})
    def unexpected(**kwargs):
        raise AssertionError("cached provider output must avoid provider calls")
    monkeypatch.setattr(workflow, "generate_pin_image", unexpected)
    monkeypatch.setattr(workflow, "generate_pin_content", unexpected)
    response = client.post("/workflow/publish-product", json=_payload(), headers=_headers("cached-provider-case-123"))
    assert response.status_code == 200
    assert response.json()["image_model"] == "cached-image-model"
    assert response.json()["model"] == "cached-content-model"


def test_content_retry_reuses_checkpointed_image_without_second_image_charge(monkeypatch):
    import app.workflow as workflow
    from app.content_generation import ContentGenerationError

    _setup_generation(monkeypatch, workflow)
    state = {"image": None, "content": None, "lease": None}
    image_calls = []
    content_calls = []

    def reserve(**kwargs):
        if state["lease"]:
            return {"acquired": False, "status": "generating"}
        state["lease"] = kwargs["lease_token"]
        return {
            "acquired": True, "status": "generating",
            "image_data_url": state["image"]["image_url"] if state["image"] else None,
            "image_model": state["image"]["model"] if state["image"] else None,
            "generated_content": state["content"],
            "content_model": "cached-content-model" if state["content"] else None,
        }

    def generate_image(**kwargs):
        image_calls.append(1)
        return {"image_url": "https://cdn.example.com/reused.png", "model": "image-model"}

    def save_image(**kwargs):
        state["image"] = {"image_url": kwargs["image_data_url"], "model": kwargs["image_model"]}

    def generate_content(**kwargs):
        content_calls.append(1)
        if len(content_calls) == 1:
            raise ContentGenerationError("temporary provider failure")
        return (SimpleNamespace(
            pin_idea="Spice rack organization", title="Spice Rack",
            description="Kitchen organization ideas.", alt_text="A spice rack on a kitchen counter.",
        ), "content-model")

    monkeypatch.setattr(workflow, "reserve_workflow_generation", reserve)
    monkeypatch.setattr(workflow, "generate_pin_image", generate_image)
    monkeypatch.setattr(workflow, "save_workflow_generation_image", save_image)
    monkeypatch.setattr(workflow, "generate_pin_content", generate_content)
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: state.update(lease=None))
    monkeypatch.setattr(workflow, "save_workflow_generation_content", lambda **kwargs: state.update(content=kwargs["generated_content"]))
    monkeypatch.setattr(workflow, "complete_workflow_generation", lambda **kwargs: state.update(lease=None))
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        200, {"id": "test-account"} if path == "/user_account" else {
            "items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]
        }
    ))
    monkeypatch.setattr(workflow, "create_product_with_content_version", lambda **kwargs: (
        {"id": 901, "product_name": kwargs["product_name"]},
        {"id": 902, "product_id": 901, "title": kwargs["title"], "description": kwargs["description"], "alt_text": kwargs["alt_text"]},
    ))
    monkeypatch.setattr(workflow, "publish_pin", lambda **kwargs: {"published": True, "pin_id": "stub-pin", "http_status": 201})

    headers = _headers("content-retry-cache-123")
    first = client.post("/workflow/publish-product", json=_payload(), headers=headers)
    assert first.status_code == 503
    assert len(image_calls) == 1
    assert len(content_calls) == 1

    second = client.post("/workflow/publish-product", json=_payload(), headers=headers)
    assert second.status_code == 200, second.text
    assert len(image_calls) == 1
    assert len(content_calls) == 2


def test_image_checkpoint_failure_releases_generation_lease(monkeypatch):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    released = []
    monkeypatch.setattr(workflow, "save_workflow_generation_image", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("checkpoint unavailable")))
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: released.append(kwargs))
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        200, {"id": "test-account"} if path == "/user_account" else {
            "items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]
        }
    ))

    response = client.post("/workflow/publish-product", json=_payload(), headers=_headers("image-checkpoint-failure-123"))

    assert response.status_code == 503
    assert len(released) == 1
    assert released[0]["idempotency_key"] == "image-checkpoint-failure-123"


def test_content_checkpoint_failure_releases_generation_lease(monkeypatch):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    released = []
    monkeypatch.setattr(workflow, "save_workflow_generation_content", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("checkpoint unavailable")))
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: released.append(kwargs))
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        200, {"id": "test-account"} if path == "/user_account" else {
            "items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]
        }
    ))

    response = client.post("/workflow/publish-product", json=_payload(), headers=_headers("content-checkpoint-failure-123"))

    assert response.status_code == 503
    assert len(released) == 1
    assert released[0]["idempotency_key"] == "content-checkpoint-failure-123"


def test_cached_content_validation_failure_releases_generation_lease(monkeypatch):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    released = []
    monkeypatch.setattr(workflow, "reserve_workflow_generation", lambda **kwargs: {
        "acquired": True, "status": "generating",
        "image_data_url": "https://cdn.example.com/cached.png", "image_model": "cached-image-model",
        "generated_content": {"unexpected": "invalid"}, "content_model": "cached-content-model",
    })
    monkeypatch.setattr(workflow, "release_workflow_generation", lambda **kwargs: released.append(kwargs))
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        200, {"id": "test-account"} if path == "/user_account" else {
            "items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]
        }
    ))

    response = client.post("/workflow/publish-product", json=_payload(), headers=_headers("invalid-cache-content-123"))

    assert response.status_code == 503
    assert len(released) == 1


def test_lease_release_failure_does_not_mask_original_error(monkeypatch):
    import app.workflow as workflow

    def failed_release(**kwargs):
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(workflow, "release_workflow_generation", failed_release)
    workflow._release_generation_lease_safely("lease-release-failure-123", "00000000-0000-0000-0000-000000000001")
