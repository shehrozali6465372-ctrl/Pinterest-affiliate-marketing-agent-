import json

import pytest

from app.config import settings
from app.content_generation import (
    AFFILIATE_DISCLOSURE,
    ContentGenerationError,
    generate_pin_content,
)

PRODUCT = {
    "product_name": "Wooden spice rack",
    "product_details": "Wall-mounted rack with six jars",
    "image_url": "data:image/png;base64,ZmFrZS1pbWFnZS1ieXRlcw==",
}


class FakeResponse:
    status_code = 200
    headers = {"content-type": "application/json"}
    content = b'{"choices":[]}'

    def __init__(self, content, finish_reason="stop", *, json_error=None):
        self.model_content = content
        self.finish_reason = finish_reason
        self.json_error = json_error

    def raise_for_status(self):
        return None

    def json(self):
        if self.json_error:
            raise self.json_error
        return {
            "choices": [{
                "finish_reason": self.finish_reason,
                "message": {"content": self.model_content},
            }]
        }


def _install_fake_client(monkeypatch, fake_response, calls):
    class FakeClient:
        def __init__(self, timeout):
            calls["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, headers, json):
            calls.update(endpoint=endpoint, headers=headers, payload=json)
            return fake_response

    monkeypatch.setattr("app.content_generation.httpx.Client", FakeClient)


def _valid_model_json():
    return json.dumps({
        "pin_idea": "Style the rack on an organized counter.",
        "title": "Organized Spice Rack",
        "description": "A tidy way to arrange everyday spices. " + AFFILIATE_DISCLOSURE,
        "alt_text": "A wooden rack holding spice jars on a kitchen wall.",
    })


def test_deepseek_request_disables_thinking_for_structured_output(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    monkeypatch.setattr(settings, "llm_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "llm_model", "deepseek-flash")
    calls = {}
    _install_fake_client(monkeypatch, FakeResponse(_valid_model_json()), calls)

    generated, model = generate_pin_content(**PRODUCT)

    assert model == "deepseek-flash"
    assert generated.title == "Organized Spice Rack"
    assert calls["payload"]["response_format"] == {"type": "json_object"}
    assert calls["payload"]["thinking"] == {"type": "disabled"}
    assert calls["payload"]["max_tokens"] == 2400
    assert calls["payload"]["stream"] is False
    assert calls["payload"]["messages"][1]["content"][1]["type"] == "image_url"


def test_truncated_json_reports_token_limit_without_logging_content(monkeypatch, caplog):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    calls = {}
    _install_fake_client(monkeypatch, FakeResponse('{"title":', "length"), calls)

    with pytest.raises(ContentGenerationError, match="token limit"):
        generate_pin_content(**PRODUCT)

    assert "DeepSeek content truncated: finish_reason=length" in caplog.text
    assert '{"title":' not in caplog.text


def test_invalid_model_json_has_a_distinct_sanitized_log(monkeypatch, caplog):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    calls = {}
    _install_fake_client(monkeypatch, FakeResponse("not-json-content", "stop"), calls)

    with pytest.raises(ContentGenerationError, match="invalid JSON content"):
        generate_pin_content(**PRODUCT)

    assert "DeepSeek model JSON parse failure" in caplog.text
    assert "not-json-content" not in caplog.text


def test_invalid_api_envelope_is_distinguished_from_model_json(monkeypatch, caplog):
    monkeypatch.setattr(settings, "llm_api_key", "unit-test-secret")
    calls = {}
    bad_json = json.JSONDecodeError("bad envelope", "not-json", 0)
    _install_fake_client(monkeypatch, FakeResponse("", json_error=bad_json), calls)

    with pytest.raises(ContentGenerationError, match="invalid JSON response envelope"):
        generate_pin_content(**PRODUCT)

    assert "DeepSeek API response JSON failure" in caplog.text
    assert "response_bytes=" in caplog.text
    assert "not-json" not in caplog.text
