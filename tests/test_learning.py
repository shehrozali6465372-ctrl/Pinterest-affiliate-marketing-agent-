import json
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
            return {"all": {"summary_metrics": {
                "IMPRESSION": 100, "SAVE": 8, "PIN_CLICK": 20, "OUTBOUND_CLICK": 5,
                "SAVE_RATE": 0.08, "USER_FOLLOW": 4, "PROFILE_VISIT": 6,
            }}}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, url, *, headers, params):
            assert url.endswith("/pins/pin-123/analytics")
            assert headers["Authorization"] == "Bearer private-token"
            assert params["metric_types"] == ",".join(learning.METRICS)
            return FakeResponse()

    monkeypatch.setattr(database, "connection", lambda: FakeConnection())
    monkeypatch.setattr(learning.httpx, "Client", FakeClient)
    result = learning.run_learning_loop(learning.LearningRequest(account_id="pinterest:account-a"))
    assert result["ok"] is True
    assert result["snapshots_saved"] == 1
    assert result["aggregate_metrics"]["impressions"] == 100
    assert result["aggregate_metrics"]["saves"] == 8
    assert result["aggregate_metrics"]["outbound_clicks"] == 5
    assert result["aggregate_metrics"]["profile_visits"] == 6
    assert result["aggregate_metrics"]["follows"] == 4
    assert result["aggregate_metrics"]["engagements"] == 33
    assert result["aggregate_metrics"]["engagement_rate"] == 0.33
    assert result["pin_results"][0]["outbound_click_rate"] == 0.05
    assert len(writes) == 1
    stored_metrics = json.loads(writes[0][1][4])
    assert stored_metrics["engagements"] == 33
    assert stored_metrics["engagement_rate"] == 0.33
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
                # OUTBOUND_CLICK omitted by Pinterest when no data is returned.
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



def test_ad_account_listing_fails_closed_without_ads_read_scope(monkeypatch):
    monkeypatch.setattr(
        learning, "get_pinterest_credential",
        lambda account_id: {"access_token": "never-print", "scope": "pins:read user_accounts:read"},
    )
    result = learning.list_ad_accounts("pinterest:account-a")
    assert result["ok"] is False
    assert result["requires_scope"] == "ads:read"
    assert result["ad_accounts"] == []


def test_audience_insights_persist_aggregated_total_and_engaged_snapshots(monkeypatch):
    monkeypatch.setattr(
        learning, "get_pinterest_credential",
        lambda account_id: {"access_token": "private-token", "scope": "user_accounts:read ads:read"},
    )
    writes = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, query, params=None):
            writes.append((query, params))
            return type("Result", (), {})()

    class Response:
        is_success = True
        status_code = 200
        def __init__(self, audience_type): self.audience_type = audience_type
        def json(self):
            return {
                "size": 1200 if self.audience_type == "YOUR_TOTAL_AUDIENCE" else 340,
                "size": 1200 if self.audience_type == "YOUR_TOTAL_AUDIENCE" else 340,
                "categories": [{"name": "Home Decor", "ratio": 0.4}],
                "demographics": {
                    "ages": [{"name": "25-34", "ratio": 0.5}],
                    "genders": [{"name": "Female", "ratio": 0.6}, {"name": "Unspecified & custom", "ratio": 0.4}],
                    "devices": [{"name": "iPhone", "ratio": 0.7}, {"name": "Android Mobile", "ratio": 0.3}],
                    "countries": [{"name": "United States", "ratio": 0.8}],
                    "metros": [{"name": "New York", "ratio": 0.2}],
                },
            }

    class Client:
        def __init__(self, *args, **kwargs): self.calls = []
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def get(self, url, *, headers, params):
            assert "/ad_accounts/123456789/audience_insights" in url
            assert headers["Authorization"] == "Bearer private-token"
            self.calls.append(params["audience_insight_type"])
            return Response(params["audience_insight_type"])

    monkeypatch.setattr(database, "connection", lambda: Conn())
    monkeypatch.setattr(learning.httpx, "Client", Client)
    result = learning.run_audience_insights("pinterest:account-a", "123456789")
    assert result["ok"] is True
    assert result["snapshots_saved"] == 2
    assert {x["audience_insight_type"] for x in result["audience_insights"]} == {
        "YOUR_TOTAL_AUDIENCE", "YOUR_ENGAGED_AUDIENCE",
    }
    assert len(writes) == 2
    assert all("pinterest_audience_insight_snapshots" in q for q, _ in writes)
    total = next(x for x in result["audience_insights"] if x["audience_insight_type"] == "YOUR_TOTAL_AUDIENCE")
    assert total["breakdown"]["countries"][0] == {"name": "United States", "percentage": 80.0, "count": None}
    assert total["breakdown"]["cities_or_metros"][0]["name"] == "New York"
    assert total["breakdown"]["age_groups"][0]["name"] == "25-34"
    assert total["breakdown"]["gender"][1]["name"] == "Unspecified & custom"
    assert total["breakdown"]["devices"][0]["name"] == "iPhone"


def test_audience_insights_rejects_invalid_ad_account_id(monkeypatch):
    monkeypatch.setattr(
        learning, "get_pinterest_credential",
        lambda account_id: {"access_token": "private-token", "scope": "ads:read"},
    )
    import pytest
    with pytest.raises(ValueError):
        learning.run_audience_insights("pinterest:account-a", "not-an-id")
