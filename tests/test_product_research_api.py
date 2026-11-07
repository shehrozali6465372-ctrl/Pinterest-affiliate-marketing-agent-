from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app import ucos_browser_client

client = TestClient(app)


def setup_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")


def test_product_research_requires_api_key(monkeypatch):
    setup_key(monkeypatch)
    response = client.post("/product-research", json={
        "source": "approved-catalog", "marketplace": "US", "search_query": "spice rack"
    })
    assert response.status_code == 401


def test_product_research_calls_browser_gateway(monkeypatch):
    setup_key(monkeypatch)
    seen = {}
    def fake_research(**kwargs):
        seen.update(kwargs)
        return {"status": "completed", "result_count": 1, "products": [{"title": "Rack"}]}
    monkeypatch.setattr(ucos_browser_client, "research_product", fake_research)
    response = client.post("/product-research", headers={"X-API-Key": "test-api-key"}, json={
        "source": "approved-catalog", "marketplace": "US", "search_query": "spice rack", "limit": 3
    })
    assert response.status_code == 200
    assert response.json()["result_count"] == 1
    assert seen["source"] == "approved-catalog"
    assert seen["search_query"] == "spice rack"
    assert seen["limit"] == 3


def test_product_research_rejects_query_and_url_together(monkeypatch):
    setup_key(monkeypatch)
    response = client.post("/product-research", headers={"X-API-Key": "test-api-key"}, json={
        "source": "approved-catalog", "marketplace": "US", "search_query": "spice rack",
        "product_url": "https://example.com/item"
    })
    assert response.status_code == 422


def test_product_research_provider_unavailable_is_fail_closed(monkeypatch):
    setup_key(monkeypatch)
    def unavailable(**kwargs):
        raise ucos_browser_client.UCOSBrowserError("browser_service_unavailable")
    monkeypatch.setattr(ucos_browser_client, "research_product", unavailable)
    response = client.post("/product-research", headers={"X-API-Key": "test-api-key"}, json={
        "source": "approved-catalog", "marketplace": "US", "search_query": "spice rack"
    })
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "product_research_unavailable"



def test_amazon_affiliate_url_requires_api_key(monkeypatch):
    setup_key(monkeypatch)
    response = client.post("/amazon-affiliate-url", json={"keyword": "spice rack"})
    assert response.status_code == 401


def test_amazon_affiliate_url_returns_only_url(monkeypatch):
    setup_key(monkeypatch)
    monkeypatch.setattr(ucos_browser_client, "amazon_affiliate_url", lambda **kwargs: "https://www.amazon.com/dp/B000000000?tag=site-20")
    response = client.post("/amazon-affiliate-url", headers={"X-API-Key": "test-api-key"}, json={"keyword": "  spice rack  "})
    assert response.status_code == 200
    assert response.json() == {"affiliate_url": "https://www.amazon.com/dp/B000000000?tag=site-20"}


def test_amazon_affiliate_url_reports_disabled_browser_access(monkeypatch):
    setup_key(monkeypatch)
    def blocked(**kwargs):
        raise ucos_browser_client.UCOSBrowserError("browser_service_access_blocked")
    monkeypatch.setattr(ucos_browser_client, "amazon_affiliate_url", blocked)
    response = client.post("/amazon-affiliate-url", headers={"X-API-Key": "test-api-key"}, json={"keyword": "spice rack"})
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "browser_service_access_blocked"
