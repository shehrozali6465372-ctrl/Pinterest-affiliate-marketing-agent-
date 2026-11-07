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


def test_amazon_keyword_returns_only_affiliate_url_and_uses_agent_endpoint(monkeypatch):
    configure(monkeypatch)
    seen = {}
    affiliate_url = "https://www.amazon.com/dp/B000000000?tag=site-20&linkCode=ogi"
    class Client:
        def __init__(self, **kwargs):
            seen["read_timeout"] = kwargs["timeout"].read
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            seen.update(url=url, **kwargs)
            return httpx.Response(200, json={
                "state": "completed", "result": {"affiliate_url": affiliate_url}
            }, request=httpx.Request("POST", url))
    monkeypatch.setattr(browser.httpx, "Client", Client)
    result = browser.amazon_affiliate_url(keyword="  spice rack  ")
    assert result == affiliate_url
    assert seen["url"].endswith("/tool/amazon/product")
    assert seen["json"] == {
        "profile_ref": "amazon-primary", "marketplace": "amazon.com",
        "keyword": "spice rack", "timeout_ms": 30000,
    }
    assert seen["read_timeout"] == 75.0


def test_amazon_keyword_rejects_invalid_or_missing_affiliate_url(monkeypatch):
    configure(monkeypatch)
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            return httpx.Response(200, json={"state": "completed", "result": {"affiliate_url": "https://example.com/not-affiliate"}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(browser.httpx, "Client", Client)
    with pytest.raises(browser.UCOSBrowserError, match="affiliate_url_invalid"):
        browser.amazon_affiliate_url(keyword="spice rack")


def test_amazon_keyword_validates_input(monkeypatch):
    configure(monkeypatch)
    with pytest.raises(ValueError, match="keyword is required"):
        browser.amazon_affiliate_url(keyword="  ")
    with pytest.raises(ValueError, match="unsupported Amazon marketplace"):
        browser.amazon_affiliate_url(keyword="rack", marketplace="example.com")


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
