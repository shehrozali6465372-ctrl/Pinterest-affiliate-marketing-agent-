from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app import trends


@contextmanager
def fake_connection():
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, *args): return None
    yield Conn()


def test_fetch_trends_returns_live_provider_values_and_persists(monkeypatch):
    monkeypatch.setattr(trends, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "user_accounts:read pins:read"
    })
    monkeypatch.setattr("app.database.connection", fake_connection)
    response = Mock(is_success=True)
    response.json.return_value = {"trends": [{
        "keyword": "kitchen organization ideas", "pct_growth_wow": 42,
        "pct_growth_mom": 85, "pct_growth_yoy": 120,
        "time_series": {"2026-10-26": 25, "2026-11-02": 40},
    }]}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get.return_value = response
    monkeypatch.setattr(trends.httpx, "Client", Mock(return_value=client))

    result = trends.fetch_trends("pinterest:123", ["US"], 50)

    assert result["ok"] is True
    assert result["source"] == "Pinterest Trends API v5"
    trend = result["regions"][0]["trends"][0]
    assert trend["keyword"] == "kitchen organization ideas"
    assert trend["growth_week_over_week_pct"] == 42
    assert trend["weekly_relative_search_interest"]["2026-11-02"] == 40
    client.get.assert_called_once()
    assert "/trends/keywords/US/top/growing" in client.get.call_args.args[0]


def test_fetch_trends_fails_closed_when_scope_missing(monkeypatch):
    monkeypatch.setattr(trends, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "pins:read"
    })
    result = trends.fetch_trends("pinterest:123", ["US"])
    assert result["ok"] is False
    assert result["requires_scope"] == "user_accounts:read"


def test_fetch_trends_rejects_unsupported_region_before_network(monkeypatch):
    monkeypatch.setattr(trends, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "user_accounts:read"
    })
    with pytest.raises(ValueError, match="Only unique supported regions"):
        trends.fetch_trends("pinterest:123", ["PK"])


def test_normalize_trend_rejects_missing_keyword():
    with pytest.raises(ValueError, match="malformed trend item"):
        trends._normalize_trend({"pct_growth_wow": 10}, 1, "US")
