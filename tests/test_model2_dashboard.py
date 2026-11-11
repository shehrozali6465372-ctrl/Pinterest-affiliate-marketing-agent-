from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app import dashboard


def _client(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "model2-dashboard-test-key")
    client = TestClient(app, base_url="https://testserver")
    login = client.post(
        "/dashboard/session",
        json={"api_key": "model2-dashboard-test-key"},
    )
    assert login.status_code == 200
    return client


def test_model2_dashboard_endpoint_requires_existing_dashboard_session(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "model2-dashboard-test-key")
    client = TestClient(app, base_url="https://testserver")

    response = client.get("/dashboard/api/model2")

    assert response.status_code == 401


def test_model2_dashboard_handles_database_without_registry_schema(monkeypatch):
    client = _client(monkeypatch)

    class FakeConnection:
        def execute(self, query, params=None):
            assert query.lstrip().startswith("SELECT")
            return SimpleNamespace(
                fetchone=lambda: {
                    "profiles": False,
                    "assignments": False,
                    "niches": False,
                    "attributions": False,
                    "learning": False,
                }
            )

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(dashboard, "connection", fake_connection)

    response = client.get("/dashboard/api/model2")

    assert response.status_code == 200
    assert response.json() == {"schema_available": False, "accounts": []}
    assert response.headers["cache-control"] == "no-store"


def test_model2_dashboard_serializes_only_nonsecret_account_and_niche_fields(monkeypatch):
    client = _client(monkeypatch)
    queries = []

    class FakeConnection:
        def execute(self, query, params=None):
            queries.append(query)
            if "to_regclass" in query:
                return SimpleNamespace(
                    fetchone=lambda: {
                        "profiles": True,
                        "assignments": True,
                        "niches": True,
                        "attributions": True,
                        "learning": True,
                    }
                )
            return SimpleNamespace(
                fetchall=lambda: [
                    {
                        "account_id": "pinterest:123456789",
                        "account_display_name": "Home Account",
                        "account_status": "active",
                        "timezone": "America/New_York",
                        "niche_id": 7,
                        "niche_slug": "home-decor",
                        "niche_display_name": "Home Decor",
                        "default_region": "US",
                        "niche_status": "archived",
                        "assignment_status": "paused",
                        "is_primary": True,
                        "attributed_publication_count": 3,
                        "snapshot_count": 2,
                        "latest_period_end": date(2026, 10, 30),
                        "latest_metrics": {
                            "impression": 100,
                            "save": None,
                            "pin_click": 4,
                            "outbound_click": 5,
                        },
                    },
                    {
                        "account_id": "pinterest:987654321",
                        "account_display_name": "",
                        "account_status": "paused",
                        "timezone": "UTC",
                        "niche_id": None,
                        "niche_slug": None,
                        "niche_display_name": None,
                        "default_region": None,
                        "niche_status": None,
                        "assignment_status": None,
                        "is_primary": None,
                        "attributed_publication_count": 0,
                        "snapshot_count": 0,
                        "latest_period_end": None,
                        "latest_metrics": None,
                    },
                ]
            )

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(dashboard, "connection", fake_connection)

    response = client.get("/dashboard/api/model2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_available"] is True
    assert payload["accounts"][0]["niche_status"] == "archived"
    assert payload["accounts"][0]["assignment_status"] == "paused"
    assert payload["accounts"][0]["latest_metrics"]["save"] is None
    assert payload["accounts"][1]["niche_id"] is None
    assert "access_token" not in response.text
    assert "test-ciphertext" not in response.text
    assert "affiliate_url" not in response.text
    assert all(query.lstrip().startswith("SELECT") for query in queries)


def test_dashboard_page_contains_model2_read_only_panel():
    client = TestClient(app, base_url="https://testserver")

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Model 2 · Accounts & niche intelligence" in response.text
    assert "/dashboard/api/model2" in response.text
    assert "Model 2 registry schema is not installed" in response.text
