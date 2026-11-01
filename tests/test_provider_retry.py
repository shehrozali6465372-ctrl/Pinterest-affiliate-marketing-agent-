from types import SimpleNamespace

import pytest

from app.config import settings
from app.media_generation import ImageGenerationError, generate_and_host_pin_image
from app.provider_retry import retry_delay_seconds


def test_retry_after_seconds_is_honored_and_bounded():
    response = SimpleNamespace(headers={"retry-after": "3"})
    assert retry_delay_seconds(response, 1) == 3
    assert retry_delay_seconds(response, 1, max_retry_after=2) is None


def test_retry_after_http_date_is_parsed(monkeypatch):
    response = SimpleNamespace(headers={"retry-after": "Thu, 01 Jan 1970 00:00:03 GMT"})
    assert 1.0 <= retry_delay_seconds(response, 1) <= 1.25


class FakeResponse:
    def __init__(self, status_code, *, body=None, headers=None, content=b""):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {"content-type": "application/json"}
        self.content = content
        self.is_error = status_code >= 400
        self.is_success = status_code < 400

    def json(self):
        return self._body


def _configure_cloudflare(monkeypatch):
    monkeypatch.setattr(settings, "cloudflare_api_token", "unit-test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "unit-test-account")
    monkeypatch.setattr(settings, "cloudflare_image_model", "@cf/test-model")


def test_cloudflare_503_retries_once_then_returns_image(monkeypatch):
    import base64
    _configure_cloudflare(monkeypatch)
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 2048
    success = FakeResponse(200, body={"result": {"image": base64.b64encode(image_bytes).decode()}})
    failures = FakeResponse(503, body={"errors": [{"code": 1234}]})
    responses = [failures, success]
    calls = []

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs):
            calls.append(True)
            return responses.pop(0)

    monkeypatch.setattr("app.media_generation.httpx.Client", FakeClient)
    monkeypatch.setattr("app.media_generation.time.sleep", lambda seconds: None)
    result = generate_and_host_pin_image(product_name="Rack", product_details="Wood")
    assert result["image_url"].startswith("data:image/png;base64,")
    assert "cloudflare_image_id" not in result
    assert len(calls) == 2


@pytest.mark.parametrize("code", [3036, 9999])
def test_cloudflare_429_non_capacity_error_is_not_retried(monkeypatch, code):
    _configure_cloudflare(monkeypatch)
    calls = []
    response = FakeResponse(429, body={"errors": [{"code": code}]})

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs):
            calls.append(True)
            return response

    monkeypatch.setattr("app.media_generation.httpx.Client", FakeClient)
    with pytest.raises(ImageGenerationError, match="HTTP 429"):
        generate_and_host_pin_image(product_name="Rack", product_details="Wood")
    assert len(calls) == 1


def test_cloudflare_capacity_429_retries_once(monkeypatch):
    import base64
    _configure_cloudflare(monkeypatch)
    image_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 2048
    responses = [
        FakeResponse(429, body={"errors": [{"code": 3040}]}),
        FakeResponse(200, body={"result": {"image": base64.b64encode(image_bytes).decode()}}),
    ]
    calls = []

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs):
            calls.append(True)
            return responses.pop(0)

    monkeypatch.setattr("app.media_generation.httpx.Client", FakeClient)
    monkeypatch.setattr("app.media_generation.time.sleep", lambda seconds: None)
    result = generate_and_host_pin_image(product_name="Rack", product_details="Wood")
    assert result["model"] == "@cf/test-model"
    assert result["image_url"].startswith("data:image/png;base64,")
    assert len(calls) == 2
