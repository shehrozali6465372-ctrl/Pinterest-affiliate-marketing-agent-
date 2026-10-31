from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("GET", "https://api-sandbox.pinterest.com/v5/catalogs")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("provider error", request=request, response=response)

    def json(self):
        return self._body


class FakeClient:
    calls = []

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return FakeResponse(200, {"items": [], "bookmark": None})

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse(200, {"batch_id": "123456789", "status": "PROCESSING", "items": [{"status": "PROCESSING"}]})


def test_sandbox_catalog_smoke_uses_only_sandbox_and_returns_batch_id(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    monkeypatch.setattr(settings, "pinterest_sandbox_access_token", "sandbox-secret")
    FakeClient.calls = []
    import app.main
    monkeypatch.setattr(app.main.httpx, "Client", FakeClient)

    response = client.post("/diagnostics/pinterest/catalog-sandbox", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "pinterest_sandbox"
    assert body["batch_id"] == "123456789"
    assert body["production_touched"] is False
    assert body["pin_published"] is False
    assert FakeClient.calls[0][0] == "GET"
    assert FakeClient.calls[0][1] == "https://api-sandbox.pinterest.com/v5/catalogs"
    assert FakeClient.calls[1][0] == "POST"
    assert FakeClient.calls[1][1] == "https://api-sandbox.pinterest.com/v5/catalogs/items/batch"
    assert FakeClient.calls[1][2]["json"]["items"][0]["operation"] == "CREATE"
    assert "sandbox-secret" not in response.text


def test_sandbox_catalog_smoke_fails_closed_without_sandbox_token(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    monkeypatch.setattr(settings, "pinterest_sandbox_access_token", None)
    monkeypatch.delenv("PINTEREST_SANDBOX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("PINTEREST_SANDBOX_TOKEN", raising=False)
    monkeypatch.delenv("PINTEREST_SANDBOX_API_TOKEN", raising=False)

    response = client.post("/diagnostics/pinterest/catalog-sandbox", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_sandbox_batch_status_rejects_non_numeric_id_before_network(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    monkeypatch.setattr(settings, "pinterest_sandbox_access_token", "sandbox-secret")

    response = client.get("/diagnostics/pinterest/catalog-sandbox/not-a-number", headers={"X-API-Key": "test-api-key"})

    assert response.status_code == 422
