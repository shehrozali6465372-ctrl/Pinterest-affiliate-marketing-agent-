import json

import httpx
import pytest

from app.config import settings
from app.content_generation import AFFILIATE_DISCLOSURE, ContentGenerationError, generate_pin_content


PRODUCT = {
    "product_name": "Wooden spice rack",
    "product_details": "Wall-mounted rack with six jars",
    "image_url": "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw==",
}


def _valid_model_json():
    return json.dumps({
        "pin_idea": "Style the rack on an organized counter.",
        "title": "Organized Spice Rack",
        "description": "A tidy way to arrange everyday spices. " + AFFILIATE_DISCLOSURE,
        "alt_text": "A wooden rack holding spice jars on a kitchen wall.",
    })


def test_transient_http_failure_logs_sanitized_correlation_metadata(monkeypatch, caplog):
    secret = "unit-test-api-secret"
    monkeypatch.setattr(settings, "llm_api_key", secret)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    first = httpx.Response(
        503,
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        headers={"content-type": "application/json", "x-request-id": "req/123"},
        json={"error": {"type": "server_error", "message": f"private-body-{secret}"}},
    )
    second = httpx.Response(
        200,
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        headers={"content-type": "application/json"},
        json={"choices": [{"finish_reason": "stop", "message": {"content": _valid_model_json()}}]},
    )
    responses = [first, second]
    calls = []

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.append({"endpoint": endpoint, "payload": json})
            return responses.pop(0)

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)

    generated, _ = generate_pin_content(**PRODUCT)

    assert generated.title == "Organized Spice Rack"
    assert len(calls) == 2
    assert "status=503" in caplog.text
    assert "provider_code=server_error" in caplog.text
    assert "attempt=1" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "content_type=application/json" in caplog.text
    assert "response_bytes=" in caplog.text
    assert "request_id=req_123" in caplog.text
    assert secret not in caplog.text
    assert "private-body" not in caplog.text


def test_http_failure_redacts_secret_reflected_in_provider_metadata(monkeypatch, caplog):
    secret = "unit-test-api-secret"
    monkeypatch.setattr(settings, "llm_api_key", secret)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    response = httpx.Response(
        503,
        request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
        headers={
            "content-type": f"application/{secret}",
            "x-request-id": secret,
        },
        json={"error": {"type": secret, "message": f"private-body-{secret}"}},
    )

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            return response

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)

    with pytest.raises(ContentGenerationError) as caught:
        generate_pin_content(**PRODUCT)

    assert secret not in caplog.text
    assert secret not in str(caught.value)
    assert f"private-body-{secret}" not in caplog.text
    assert "provider_code=_REDACTED_" in caplog.text
    assert "content_type=application/_REDACTED_" in caplog.text
    assert "request_id=_REDACTED_" in caplog.text



def test_invalid_json_retry_exhaustion_redacts_secret_from_content_type(monkeypatch, caplog):
    secret = "unit-test-api-secret"
    monkeypatch.setattr(settings, "llm_api_key", secret)
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    responses = [
        httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
            headers={"content-type": f"application/{secret}", "x-request-id": "envelope/456"},
            content=b"not-json",
        )
        for _ in range(2)
    ]

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            return responses.pop(0)

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)

    with pytest.raises(ContentGenerationError, match="invalid JSON response envelope"):
        generate_pin_content(**PRODUCT)

    assert secret not in caplog.text
    assert "content_type=application/_REDACTED_" in caplog.text
    assert "response_bytes=8" in caplog.text
    assert "duration_ms=" in caplog.text
    assert "request_id=envelope_456" in caplog.text
