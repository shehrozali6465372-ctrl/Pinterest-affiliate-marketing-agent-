"""Authenticated, provider-neutral client for the UCOS Personal Browser service.

This module deliberately does not publish Pins, access browser persistence, or
fall back to scraping. Callers must separately enforce product-source policy.
"""
from __future__ import annotations

import hmac
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.config import settings


class UCOSBrowserError(RuntimeError):
    """Safe, classified browser-service integration error."""


def _request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = (settings.ucos_browser_base_url or "").strip().rstrip("/")
    token = settings.ucos_browser_agent_token or ""
    if not base_url or not token:
        raise UCOSBrowserError("browser_service_not_configured")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise UCOSBrowserError("browser_service_url_invalid")
    try:
        with httpx.Client(timeout=httpx.Timeout(40.0, connect=8.0), follow_redirects=False) as client:
            response = client.post(
                f"{base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
    except httpx.TimeoutException as exc:
        raise UCOSBrowserError("browser_service_timeout") from exc
    except httpx.HTTPError as exc:
        raise UCOSBrowserError("browser_service_unreachable") from exc
    if response.status_code in (401, 403):
        raise UCOSBrowserError("browser_service_auth_rejected")
    if response.status_code == 429:
        raise UCOSBrowserError("browser_service_rate_limited")
    if response.status_code == 503:
        raise UCOSBrowserError("browser_service_unavailable")
    if not response.is_success:
        raise UCOSBrowserError(f"browser_service_http_{response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise UCOSBrowserError("browser_service_invalid_json") from exc
    if not isinstance(data, dict):
        raise UCOSBrowserError("browser_service_invalid_response")
    return data


def research_product(*, source: str, marketplace: str, search_query: str | None = None,
                     product_url: str | None = None, fields: list[str] | None = None,
                     limit: int = 10, require_affiliate_link: bool = False) -> dict[str, Any]:
    """Call the explicitly registered provider research adapter; no generic scraping."""
    if bool(search_query) == bool(product_url):
        raise ValueError("exactly one of search_query or product_url is required")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    payload: dict[str, Any] = {
        "source": source, "marketplace": marketplace,
        "fields": fields or ["title", "price", "currency", "product_url", "image_url"],
        "limit": limit, "require_affiliate_link": require_affiliate_link,
    }
    if search_query:
        payload["search_query"] = search_query
    if product_url:
        payload["product_url"] = product_url
    return _request("/tool/product/research", payload)


def amazon_product(*, product_url: str, marketplace: str = "amazon.com",
                   fields: list[str] | None = None, generate_affiliate_link: bool = False,
                   timeout_ms: int = 30000) -> dict[str, Any]:
    """Call the isolated Amazon tool. The browser service's policy gate remains authoritative."""
    if not product_url.startswith("https://"):
        raise ValueError("product_url must use HTTPS")
    if not 1000 <= timeout_ms <= 60000:
        raise ValueError("timeout_ms must be between 1000 and 60000")
    return _request("/tool/amazon/product", {
        "profile_ref": "amazon-primary", "marketplace": marketplace,
        "product_url": product_url,
        "fields": fields or ["title", "price", "availability"],
        "generate_affiliate_link": generate_affiliate_link,
        "timeout_ms": timeout_ms,
    })
