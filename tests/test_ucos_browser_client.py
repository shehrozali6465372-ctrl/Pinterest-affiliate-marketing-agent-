import httpx
import pytest

from app import ucos_browser_client as browser


def configure(monkeypatch):
    monkeypatch.setattr(browser.settings, "ucos_browser_base_url", "https://ucos-personal-browser.onrender.com")
    monkeypatch.setattr(browser.settings, "ucos_browser_agent_token", "agent-secret")


def test_research_uses_agent_token_and_correct_endpoint(monkeypatch):
    configure(monkeypatch)
    seen = {}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            seen.update(url=url, **kwargs)
            return httpx.Response(200, json={"status": "completed", "products": []}, request=httpx.Request("POST", url))
    monkeypatch.setattr(browser.httpx, "Client", Client)
    result = browser.research_product(source="approved-catalog", marketplace="US", search_query="spice rack")
    assert result["status"] == "completed"
    assert seen["url"].endswith("/tool/product/research")
    assert seen["headers"]["Authorization"] == "Bearer agent-secret"
    assert "amazon-primary" not in seen["json"]


def test_missing_credentials_fail_closed(monkeypatch):
    monkeypatch.setattr(browser.settings, "ucos_browser_base_url", None)
    monkeypatch.setattr(browser.settings, "ucos_browser_agent_token", None)
    with pytest.raises(browser.UCOSBrowserError, match="not_configured"):
        browser.research_product(source="x", marketplace="US", search_query="x")


def test_research_requires_exactly_one_query_or_url(monkeypatch):
    configure(monkeypatch)
    with pytest.raises(ValueError):
        browser.research_product(source="x", marketplace="US", search_query="x", product_url="https://example.com")


def test_amazon_request_is_bounded_and_uses_agent_endpoint(monkeypatch):
    configure(monkeypatch)
    seen = {}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            seen.update(url=url, **kwargs)
            return httpx.Response(200, json={"status": "partial", "affiliate_link": None}, request=httpx.Request("POST", url))
    monkeypatch.setattr(browser.httpx, "Client", Client)
    result = browser.amazon_product(product_url="https://www.amazon.com/dp/B000000000")
    assert result["status"] == "partial"
    assert seen["url"].endswith("/tool/amazon/product")
    assert seen["json"]["profile_ref"] == "amazon-primary"
    assert seen["json"]["generate_affiliate_link"] is False


def test_redirects_are_not_followed(monkeypatch):
    configure(monkeypatch)
    class Client:
        def __init__(self, **kwargs): assert kwargs["follow_redirects"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            return httpx.Response(307, headers={"Location": "https://attacker.example"}, request=httpx.Request("POST", url))
    monkeypatch.setattr(browser.httpx, "Client", Client)
    with pytest.raises(browser.UCOSBrowserError, match="http_307"):
        browser.research_product(source="x", marketplace="US", search_query="x")
