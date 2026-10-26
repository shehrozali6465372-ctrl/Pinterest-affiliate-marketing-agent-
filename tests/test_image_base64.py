import base64

from app.pinterest import image_media_source


def test_generated_data_url_uses_pinterest_base64_source():
    image_bytes = b"\x89PNG\r\n\x1a\n" + (b"x" * 2048)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    source = image_media_source(f"data:image/png;base64,{encoded}")

    assert source["source_type"] == "image_base64"
    assert source["content_type"] == "image/png"
    assert source["data"] == encoded
    assert source["is_standard"] is True
    assert "url" not in source


def test_legacy_public_url_keeps_image_url_source():
    source = image_media_source("https://cdn.example.com/pin.png")

    assert source == {
        "source_type": "image_url",
        "url": "https://cdn.example.com/pin.png",
        "is_standard": True,
    }


def test_invalid_data_url_is_rejected_before_request():
    from app.pinterest import PinterestPublishError

    try:
        image_media_source("data:image/png;base64,not-valid***")
    except PinterestPublishError as exc:
        assert exc.error_code == "invalid_image_data"
        assert exc.outcome_uncertain is False
    else:
        raise AssertionError("invalid image data should be rejected")
