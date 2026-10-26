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
    monkeypatch.setattr(workflow, "get_pinterest_credential", lambda account_id: {"access_token": "test-token"})
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", lambda **kwargs: {
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


def test_persistence_failure_never_attempts_pin_publish(monkeypatch):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    pinterest_calls = []

    def pinterest_request(method, path, token, *, body=None):
        pinterest_calls.append((method, path))
        if path == "/user_account":
            return 200, {"id": "test-user"}
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
        {"id": 1002, "product_id": 1001},
    ))
    monkeypatch.setattr(workflow, "begin_publish_attempt", lambda **kwargs: {
        "blocked": False, "id": 1003, "status": "pending",
    })
    finished = []
    monkeypatch.setattr(workflow, "finish_publish_attempt", lambda attempt_id, **kwargs: (
        finished.append({"id": attempt_id, **kwargs}) or {
            "id": attempt_id, "status": kwargs["status"],
            "pinterest_pin_id": kwargs.get("pinterest_pin_id"),
        }
    ))

    def pinterest_request(method, path, token, *, body=None):
        if path == "/user_account":
            return 200, {"id": "test-user"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        if path == "/pins":
            raise workflow.HTTPException(status_code=502, detail="Pinterest request failed; verify the account before retrying any publish operation.")
        raise AssertionError(f"Unexpected Pinterest request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers=_headers("ambiguous-publish-retry-123"),
    )

    assert response.status_code == 502
    assert any(item.get("status") == "unknown" and item.get("error_code") == "pinterest_outcome_uncertain" for item in finished)
