"""Focused regression tests for Pinterest request failures in the E2E workflow."""

import httpx
import pytest


def test_pin_create_timeout_is_reported_as_uncertain(monkeypatch):
    import httpx
    from app.pinterest import PinterestPublishError, create_pin_request

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, *args, **kwargs): raise httpx.ReadTimeout("simulated timeout")

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    with pytest.raises(PinterestPublishError) as exc:
        create_pin_request(access_token="test-token", payload={
            "board_id": "board-1", "title": "Valid title", "description": "Valid description",
            "alt_text": "Valid alt text", "media_source": {"source_type": "image_url", "url": "https://example.com/a.jpg", "is_standard": True},
            "link": "https://example.com/product",
        })
    assert exc.value.outcome_uncertain is True


def test_pin_create_5xx_is_reported_as_uncertain(monkeypatch):
    from app.pinterest import PinterestPublishError, create_pin_request

    class FakeResponse:
        status_code = 503
        content = b'{"message":"temporary error"}'
        def json(self): return {"message": "temporary error"}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    with pytest.raises(PinterestPublishError) as exc:
        create_pin_request(access_token="test-token", payload={
            "board_id": "board-1", "title": "Valid title", "description": "Valid description",
            "alt_text": "Valid alt text", "media_source": {"source_type": "image_url", "url": "https://example.com/a.jpg", "is_standard": True},
            "link": "https://example.com/product",
        })
    assert exc.value.outcome_uncertain is True
    assert exc.value.http_status == 503


def test_pin_create_http_408_is_reported_as_uncertain(monkeypatch):
    from app.pinterest import PinterestPublishError, create_pin_request

    class FakeResponse:
        status_code = 408
        content = b'{"message":"request timeout"}'
        def json(self): return {"message": "request timeout"}

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def post(self, *args, **kwargs): return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    with pytest.raises(PinterestPublishError) as exc:
        create_pin_request(access_token="test-token", payload={
            "board_id": "board-1", "title": "Valid title", "description": "Valid description",
            "alt_text": "Valid alt text", "media_source": {"source_type": "image_url", "url": "https://example.com/a.jpg", "is_standard": True},
            "link": "https://example.com/product",
        })
    assert exc.value.outcome_uncertain is True
    assert exc.value.http_status == 408
