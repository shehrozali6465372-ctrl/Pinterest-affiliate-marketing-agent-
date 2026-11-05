import base64

import httpx
import pytest

from app.config import settings
from app.media_generation import ImageGenerationError, generate_pin_image


def _mock_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr(
        "app.media_generation.httpx.Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(settings, "cloudflare_api_token", "test-token")
    monkeypatch.setattr(settings, "cloudflare_account_id", "test-account")
    monkeypatch.setattr(settings, "cloudflare_image_model", "test-model")
    monkeypatch.setattr(settings, "cloudflare_image_max_bytes", 2048)


def test_binary_image_response_is_rejected_from_content_length_before_buffering(monkeypatch):
    image = b"x" * 2049

    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image)

    _mock_client(monkeypatch, handler)
    with pytest.raises(ImageGenerationError, match="configured size limit"):
        generate_pin_image(product_name="test", product_details="test")


def test_chunked_binary_image_response_is_rejected_while_streaming(monkeypatch):
    class OversizedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * 1500
            yield b"y" * 600

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            stream=OversizedStream(),
        )

    _mock_client(monkeypatch, handler)
    with pytest.raises(ImageGenerationError, match="configured size limit"):
        generate_pin_image(product_name="test", product_details="test")


def test_json_base64_image_over_limit_is_rejected(monkeypatch):
    oversized = base64.b64encode(b"x" * 2049).decode("ascii")

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"result": {"image": oversized}},
        )

    _mock_client(monkeypatch, handler)
    with pytest.raises(ImageGenerationError, match="configured size limit"):
        generate_pin_image(product_name="test", product_details="test")


def test_valid_streamed_binary_image_is_returned_as_data_url(monkeypatch):
    image = b"x" * 1500

    def handler(request):
        return httpx.Response(200, headers={"content-type": "image/png"}, content=image)

    _mock_client(monkeypatch, handler)
    result = generate_pin_image(product_name="test", product_details="test")
    assert result["image_url"].startswith("data:image/png;base64,")
    assert base64.b64decode(result["image_url"].split(",", 1)[1]) == image
    assert result["model"] == "test-model"


def test_image_size_limit_setting_is_bounded():
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(cloudflare_image_max_bytes=512)
    with pytest.raises(ValidationError):
        Settings(cloudflare_image_max_bytes=30 * 1024 * 1024)
