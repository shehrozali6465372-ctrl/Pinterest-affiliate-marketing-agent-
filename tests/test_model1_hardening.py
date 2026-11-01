from fastapi.testclient import TestClient

from app.config import settings
from app.learning import _extract_metrics
from app.main import app
from app import workflow


def test_operational_api_fails_closed_when_key_is_unset(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", None)
    response = TestClient(app).get("/readiness")
    assert response.status_code == 503
    assert response.json()["detail"] == "API authentication is not configured."


def test_missing_pinterest_metrics_remain_unknown():
    metrics = _extract_metrics({
        "summary_metrics": {
            "IMPRESSION": 120,
            "OUTBOUND_CLICK": 3,
        }
    })
    assert metrics == {
        "impression": 120.0,
        "save": None,
        "pin_click": None,
        "outbound_click": 3.0,
    }


def test_explicit_zero_pinterest_metric_remains_zero():
    metrics = _extract_metrics({
        "summary_metrics": {
            "IMPRESSION": 0,
            "SAVE": 0,
            "PIN_CLICK": 0,
            "OUTBOUND_CLICK": 0,
        }
    })
    assert all(value == 0 for value in metrics.values())


def test_board_resolution_checks_later_pages_before_creating(monkeypatch):
    calls = []

    def fake_request(method, path, token, *, body=None):
        calls.append((method, path, body))
        if method == "GET" and "bookmark=" not in path:
            return 200, {"items": [{"id": "board-1", "name": "Other"}], "bookmark": "page-2"}
        if method == "GET" and "bookmark=page-2" in path:
            return 200, {"items": [{"id": "board-2", "name": "Kitchen"}]}
        raise AssertionError("A board already exists; creation must not be attempted")

    monkeypatch.setattr(workflow, "_pinterest_request", fake_request)
    assert workflow._ensure_board("test-token", "Kitchen", "Kitchen board") == "board-2"
    assert len(calls) == 2
    assert all(call[0] == "GET" for call in calls)


def test_board_resolution_creates_only_after_all_pages(monkeypatch):
    calls = []

    def fake_request(method, path, token, *, body=None):
        calls.append((method, path, body))
        if method == "GET" and "bookmark=" not in path:
            return 200, {"items": [{"id": "board-1", "name": "Other"}], "bookmark": "page-2"}
        if method == "GET" and "bookmark=page-2" in path:
            return 200, {"items": []}
        if method == "POST" and path == "/boards":
            return 201, {"id": "new-board"}
        raise AssertionError(f"Unexpected request: {method} {path}")

    monkeypatch.setattr(workflow, "_pinterest_request", fake_request)
    assert workflow._ensure_board("test-token", "Kitchen", "Kitchen board") == "new-board"
    assert [call[0] for call in calls] == ["GET", "GET", "POST"]
