import pytest

from app import media_generation
from app.config import settings


class FakeResponse:
    def __init__(self, *, status_code=200, content_type="image/png", content=b"x" * 2048, body=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.content = content
        self._body = body or {}
        self.is_error = status_code >= 400
        self.is_success = status_code < 400

    def json(self):
        return self._body


def test_generated_image_is_returned_as_data_url_without_image_hosting(monkeypatch):
    import base64

    monkeypatch.setattr(settings, "cloudflare_api_token", "test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "test-account")
    monkeypatch.setattr(settings, "cloudflare_image_model", "@cf/test-image-model")
    calls = []

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            assert "/ai/run/" in url
            return FakeResponse()

    monkeypatch.setattr(media_generation.httpx, "Client", Client)
    result = media_generation.generate_and_host_pin_image(
        product_name="Spice rack",
        product_details="Three tiers for kitchen storage",
    )

    assert result["image_url"].startswith("data:image/png;base64,")
    assert base64.b64decode(result["image_url"].split(",", 1)[1]) == b"x" * 2048
    assert result["model"] == "@cf/test-image-model"
    assert result["byte_length"] == "2048"
    assert len(calls) == 1
    assert all(not url.endswith("/images/v1") for url, _ in calls)


def test_cloudflare_images_is_never_called(monkeypatch):
    monkeypatch.setattr(settings, "cloudflare_api_token", "test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "test-account")
    calls = []

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, url, **kwargs):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr(media_generation.httpx, "Client", Client)
    media_generation.generate_and_host_pin_image(product_name="Spice rack", product_details="Three tiers")
    assert len(calls) == 1
    assert "/ai/run/" in calls[0]
    assert "/images/v1" not in calls[0]


def test_generated_image_over_inline_limit_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "cloudflare_api_token", "test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "test-account")

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, url, **kwargs):
            return FakeResponse(content=b"x" * (media_generation.MAX_INLINE_IMAGE_BYTES + 1))

    monkeypatch.setattr(media_generation.httpx, "Client", Client)
    with pytest.raises(media_generation.ImageGenerationError, match="32 MiB inline-image limit"):
        media_generation.generate_and_host_pin_image(product_name="Spice rack", product_details="Three tiers")
