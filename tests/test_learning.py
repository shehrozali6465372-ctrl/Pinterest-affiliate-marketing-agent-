from app import database, learning
from app.config import settings


def test_learning_loop_filters_published_pins_by_account(monkeypatch):
    monkeypatch.setattr(learning, "get_pinterest_credential", lambda account_id: {"access_token": "private-token"})

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            assert "status = 'succeeded'" in query
            assert "account_id = %s" in query
            assert params == ("pinterest:account-a",)
            return type("Result", (), {"fetchall": lambda self: []})()

    monkeypatch.setattr(database, "connection", lambda: FakeConnection())
    result = learning.run_learning_loop(learning.LearningRequest(account_id="pinterest:account-a"))
    assert result["pins_checked"] == 0
    assert result["model_trained"] is False
    assert result["learning_status"] == "waiting_for_published_pins"


def test_learning_loop_parses_documented_pinterest_summary_metrics(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(learning, "get_pinterest_credential", lambda account_id: {"access_token": "private-token"})
    writes = []

    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            if "SELECT id AS publication_id" in query:
                assert "account_id = %s" in query
                assert params == ("pinterest:account-a",)
                return type("Result", (), {"fetchall": lambda self: [{
                    "publication_id": 7, "product_id": 2, "content_version_id": 3,
                    "pinterest_pin_id": "pin-123",
                }]})()
            writes.append((query, params))
            return type("Result", (), {})()

    class FakeResponse:
        is_success = True
        status_code = 200
        def json(self):
            return {
                "IMPRESSION": {"summary_metrics": {"impression": 100}},
                "SAVE": {"summary_metrics": {"save": 8}},
                "PIN_CLICK": {"summary_metrics": {"pin_click": 20}},
                "OUTBOUND_CLICK": {"summary_metrics": {"outbound_click": 5}},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, url, *, headers, params):
            assert url.endswith("/pins/pin-123/analytics")
            assert headers["Authorization"] == "Bearer private-token"
            assert params["metric_types"] == "IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK"
            return FakeResponse()

    monkeypatch.setattr(database, "connection", lambda: FakeConnection())
    monkeypatch.setattr(learning.httpx, "Client", FakeClient)
    result = learning.run_learning_loop(learning.LearningRequest(account_id="pinterest:account-a"))
    assert result["ok"] is True
    assert result["snapshots_saved"] == 1
    assert result["aggregate_metrics"]["impressions"] == 100
    assert result["aggregate_metrics"]["saves"] == 8
    assert result["aggregate_metrics"]["outbound_clicks"] == 5
    assert result["pin_results"][0]["outbound_click_rate"] == 0.05
    assert len(writes) == 1
    assert result["model_trained"] is False


def test_missing_requested_metric_is_not_persisted(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(learning, "get_pinterest_credential", lambda account_id: {"access_token": "unit-test"})
    writes = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            if "SELECT id AS publication_id" in query:
                return type("Rows", (), {"fetchall": lambda self: [{
                    "publication_id": 7, "product_id": 2, "content_version_id": 3,
                    "pinterest_pin_id": "pin-incomplete",
                }]})()
            writes.append(query)
            return type("Result", (), {})()

    class Response:
        is_success = True
        status_code = 200
        def json(self): return {"IMPRESSION": {"summary_metrics": {"impression": 100}}}

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, *args, **kwargs): return Response()

    monkeypatch.setattr(database, "connection", lambda: Conn())
    monkeypatch.setattr(learning.httpx, "Client", Client)
    result = learning.run_learning_loop(learning.LearningRequest(account_id="pinterest:account-a"))
    assert result["ok"] is False
    assert result["snapshots_saved"] == 0
    assert result["pin_results"][0]["ok"] is False
    assert result["pin_results"][0]["failure_stage"] == "analytics_payload"
    assert "private-token" not in str(result)
    assert writes == []


def test_learning_loop_parses_top_level_summary_metrics_and_omitted_zero_metrics(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_api_base_url", "https://api.pinterest.com/v5")
    monkeypatch.setattr(learning, "get_pinterest_credential", lambda account_id: {"access_token": "test-only"})
    writes = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            if "SELECT id AS publication_id" in query:
                return type("Rows", (), {"fetchall": lambda self: [{
                    "publication_id": 8, "product_id": 2, "content_version_id": 3,
                    "pinterest_pin_id": "pin-summary-root",
                }]})()
            writes.append((query, params))
            return type("Result", (), {})()

    class Response:
        is_success = True
        status_code = 200
        def json(self):
            return {"all": {"summary_metrics": {
                "IMPRESSION": 120, "SAVE": 9, "PIN_CLICK": 22,
            }, "daily_metrics": []}}

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, *args, **kwargs): return Response()

    monkeypatch.setattr(database, "connection", lambda: Conn())
    monkeypatch.setattr(learning.httpx, "Client", Client)
    result = learning.run_learning_loop(learning.LearningRequest(account_id="pinterest:account-a"))
    assert result["ok"] is True
    assert result["snapshots_saved"] == 1
    assert result["aggregate_metrics"]["impressions"] == 120
    assert result["aggregate_metrics"]["saves"] == 9
    assert result["pin_results"][0]["metrics"]["outbound_click"] == 0
    assert len(writes) == 1
