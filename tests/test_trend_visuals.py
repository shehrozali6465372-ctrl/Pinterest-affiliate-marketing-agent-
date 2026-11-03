from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app import trend_visuals


@contextmanager
def fake_connection():
    class Conn:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, *args): return None
    yield Conn()


def test_featured_topics_normalizes_provider_topics_and_pin_samples(monkeypatch):
    monkeypatch.setattr(trend_visuals, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "user_accounts:read pins:read"
    })
    monkeypatch.setattr("app.database.connection", fake_connection)
    response = Mock(is_success=True)
    response.json.return_value = [{
        "interest": "ALL", "market": "US", "trends": [{
            "title": "Small kitchen organization", "description": "Storage ideas",
            "percent_growth_mom": 32, "related_interests": ["Kitchen"],
            "related_searches": ["spice rack ideas"],
            "pins": [{"src": "https://i.pinimg.com/originals/example.jpg",
                      "width": 1000, "height": 1500, "color": "#aabbcc",
                      "vertical_offset": 0.2, "id": "pin-1"}]
        }]
    }]
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.get.return_value = response
    monkeypatch.setattr(trend_visuals.httpx, "Client", Mock(return_value=client))

    result = trend_visuals.fetch_featured_topics("pinterest:123", ["US"])

    assert result["ok"] is True
    topic = result["regions"][0]["topics"][0]
    assert topic["title"] == "Small kitchen organization"
    assert topic["growth_month_over_month_pct"] == 32
    assert topic["related_searches"] == ["spice rack ideas"]
    assert topic["example_pins"][0]["image_url"].startswith("https://i.pinimg.com/")
    assert topic["example_pins"][0]["dominant_color"] == "#aabbcc"
    client.get.assert_called_once()
    assert client.get.call_args.kwargs["params"] == {"interest": "ALL", "region": "US"}


def test_featured_topics_fails_closed_when_scope_missing(monkeypatch):
    monkeypatch.setattr(trend_visuals, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "pins:read"
    })
    result = trend_visuals.fetch_featured_topics("pinterest:123", ["US"])
    assert result["ok"] is False
    assert result["requires_scope"] == "user_accounts:read"


def test_featured_topics_rejects_unsupported_or_duplicate_regions(monkeypatch):
    monkeypatch.setattr(trend_visuals, "get_pinterest_credential", lambda account_id: {
        "access_token": "test-token", "scope": "user_accounts:read"
    })
    with pytest.raises(ValueError, match="Only unique supported regions"):
        trend_visuals.fetch_featured_topics("pinterest:123", ["PK"])
    with pytest.raises(ValueError, match="Only unique supported regions"):
        trend_visuals.fetch_featured_topics("pinterest:123", ["US", "US"])
