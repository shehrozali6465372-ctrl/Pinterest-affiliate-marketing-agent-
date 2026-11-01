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


def test_generated_image_is_uploaded_to_cloudflare_images(monkeypatch):
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
            if "/ai/run/" in url:
                return FakeResponse()
            return FakeResponse(body={
                "success": True,
                "result": {
                    "id": "cloudflare-image-123",
                    "variants": ["https://imagedelivery.net/account/image-123/public"],
                },
            })

    monkeypatch.setattr(media_generation.httpx, "Client", Client)
    result = media_generation.generate_and_host_pin_image(
        product_name="Spice rack",
        product_details="Three tiers for kitchen storage",
    )

    assert result["image_url"] == "https://imagedelivery.net/account/image-123/public"
    assert result["cloudflare_image_id"] == "cloudflare-image-123"
    assert result["model"] == "@cf/test-image-model"
    assert result["byte_length"] == "2048"
    assert len(calls) == 2
    assert calls[1][0].endswith("/images/v1")
    assert calls[1][1]["data"]["requireSignedURLs"] == "false"
    assert calls[1][1]["files"]["file"][2] == "image/png"


def test_cloudflare_images_upload_failure_blocks_ephemeral_publish(monkeypatch):
    monkeypatch.setattr(settings, "cloudflare_api_token", "test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "test-account")

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, url, **kwargs):
            if "/ai/run/" in url:
                return FakeResponse()
            return FakeResponse(status_code=403, body={
                "success": False,
                "errors": [{"code": 10000, "message": "Authentication error"}],
            })

    monkeypatch.setattr(media_generation.httpx, "Client", Client)
    with pytest.raises(media_generation.ImageGenerationError, match="Images upload failed"):
        media_generation.generate_and_host_pin_image(
            product_name="Spice rack",
            product_details="Three tiers",
        )
