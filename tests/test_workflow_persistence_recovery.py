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
    import base64
    monkeypatch.setattr(workflow, "generate_and_host_pin_image", lambda **kwargs: {
        "image_url": "data:image/png;base64," + base64.b64encode(b"x" * 2048).decode(),
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
    persisted_arguments = {}
    def persist(**kwargs):
        persisted_arguments.update(kwargs)
        return ({"id": 1001, "product_name": kwargs["product_name"]},
        {"id": 1002, "product_id": 1001}, {
            "id": 1003, "product_id": 1001, "content_version_id": 1002,
            "board_id": "board-1", "account_id": "pinterest:test-account", "status": "pending",
        })
    monkeypatch.setattr(workflow, "create_product_with_content_version", persist)
    monkeypatch.setattr(workflow, "_pinterest_request", lambda method, path, token, **kwargs: (
        (200, {"id": "test-user"}) if path == "/user_account" else
        (200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]})
    ))
    import app.publishing as publishing
    finished = []
    monkeypatch.setattr(publishing, "finish_publish_attempt", lambda attempt_id, **kwargs: (
        finished.append({"id": attempt_id, **kwargs}) or {
            "id": attempt_id, "status": kwargs["status"],
            "pinterest_pin_id": kwargs.get("pinterest_pin_id"),
        }
    ))
    from app.pinterest import PinterestPublishError
    monkeypatch.setattr(publishing, "create_pin_request", lambda **kwargs: (_ for _ in ()).throw(
        PinterestPublishError("transport uncertain", outcome_uncertain=True, error_code="transport_outcome_unknown")
    ))

    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers=_headers("ambiguous-publish-retry-123"),
    )

    assert response.status_code == 502
    assert persisted_arguments["image_url"] is None
    assert any(item.get("status") == "unknown" and item.get("error_code") == "transport_outcome_unknown" for item in finished)


def test_persistence_constraint_failure_logs_safe_schema_diagnostics(monkeypatch, caplog):
    from types import SimpleNamespace
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    pinterest_calls = []

    def pinterest_request(method, path, token, *, body=None):
        pinterest_calls.append(path)
        if path == "/user_account":
            return 200, {"id": "test-user"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        raise AssertionError("No Pinterest write is allowed after persistence fails")

    class SimulatedNotNullViolation(Exception):
        sqlstate = "23502"
        diag = SimpleNamespace(
            table_name="products",
            column_name="image_url",
            constraint_name="unknown",
        )

    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)

    def fail_persistence(**kwargs):
        raise SimulatedNotNullViolation("do not log raw database error or parameters")

    monkeypatch.setattr(workflow, "create_product_with_content_version", fail_persistence)
    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers=_headers("persist-not-null-diagnostics-123"),
    )

    assert response.status_code == 503
    assert "sqlstate=23502" in caplog.text
    assert "table=products" in caplog.text
    assert "column=image_url" in caplog.text
    assert "do not log raw database error" not in caplog.text
    assert all(path != "/pins" for path in pinterest_calls)


def test_idempotency_state_failure_logs_safe_stage_and_correlation_id(monkeypatch, caplog):
    import app.workflow as workflow

    monkeypatch.setattr(settings, "app_api_key", "test-api-key")

    def fail_lookup(_key):
        raise RuntimeError("private database connection string must never be logged")

    monkeypatch.setattr(workflow, "get_product_by_idempotency_key", fail_lookup)
    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers={**_headers("idempotency-failure-123"), "X-Request-ID": "trace/123"},
    )

    assert response.status_code == 503
    assert "stage=idempotency_state_read" in caplog.text
    assert "request_id=trace_123" in caplog.text
    assert "exception_type=RuntimeError" in caplog.text
    assert "private database connection string" not in caplog.text


def test_atomic_product_content_publication_reservation_failure_rolls_back_before_pin_write(monkeypatch, caplog):
    import app.workflow as workflow

    _setup_generation(monkeypatch, workflow)
    pinterest_paths = []
    def pinterest_request(method, path, token, *, body=None):
        pinterest_paths.append(path)
        if path == "/user_account":
            return 200, {"id": "test-user"}
        if path == "/boards?page_size=100":
            return 200, {"items": [{"id": "board-1", "name": "Modern Living Hub | Kitchen & Home Organization"}]}
        raise AssertionError("Pin write must not happen when atomic publication reservation fails")
    monkeypatch.setattr(workflow, "_pinterest_request", pinterest_request)
    def fail_atomic_persistence(**kwargs):
        assert kwargs["publication_board_id"] == "board-1"
        assert kwargs["publication_account_id"] == "pinterest:test-account"
        raise RuntimeError("private DB details must not be logged")
    monkeypatch.setattr(workflow, "create_product_with_content_version", fail_atomic_persistence)

    response = client.post(
        "/workflow/publish-product",
        json=_payload(),
        headers={**_headers("atomic-attempt-failure-123"), "X-Request-ID": "atomic-attempt-42"},
    )

    assert response.status_code == 503
    assert "stage=product_content_persistence" in caplog.text
    assert "request_id=atomic-attempt-42" in caplog.text
    assert "private DB details" not in caplog.text
    assert "/pins" not in pinterest_paths
