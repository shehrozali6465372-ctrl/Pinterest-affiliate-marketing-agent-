import pytest
from pydantic import ValidationError

from app.config import settings
from app.content_generation import AFFILIATE_DISCLOSURE, GeneratedContent, _with_affiliate_disclosure
from app.pin_limits import PIN_ALT_TEXT_MAX_LENGTH, PIN_DESCRIPTION_MAX_LENGTH, PIN_TITLE_MAX_LENGTH
from app.pinterest import PinterestPublishError, publish_image_pin
from app.workflow import HubPinPublishInput, _pinterest_request


def test_central_pinterest_text_limits_match_documented_api_contract():
    assert PIN_TITLE_MAX_LENGTH == 100
    assert PIN_DESCRIPTION_MAX_LENGTH == 800
    assert PIN_ALT_TEXT_MAX_LENGTH == 500


def test_generated_content_schema_rejects_description_over_pinterest_limit():
    with pytest.raises(ValidationError):
        GeneratedContent.model_validate({
            "pin_idea": "A visual concept",
            "title": "A title",
            "description": "x" * 801,
            "alt_text": "Visible image content",
        })


def test_affiliate_disclosure_is_preserved_inside_800_character_budget():
    description = _with_affiliate_disclosure("Useful kitchen organization copy. " * 100)
    assert len(description) <= PIN_DESCRIPTION_MAX_LENGTH
    assert AFFILIATE_DISCLOSURE in description


def test_existing_disclosure_is_not_duplicated():
    source = "A concise description. " + AFFILIATE_DISCLOSURE
    assert _with_affiliate_disclosure(source) == source


def test_hub_manual_pin_input_rejects_description_over_800_characters():
    with pytest.raises(ValidationError):
        HubPinPublishInput.model_validate({
            "account_id": "pinterest:test",
            "board_id": "board-test",
            "title": "Valid title",
            "description": "x" * 801,
            "alt_text": "Valid alt text",
            "image_url": "https://example.com/image.png",
            "destination_url": "https://example.com/item",
        })


def test_publish_image_pin_rejects_oversized_text_before_network_call(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", "test-token")
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def post(self, *args, **kwargs):
            calls.append(True)
            raise AssertionError("Pinterest network call must not occur")

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    with pytest.raises(PinterestPublishError, match="800-character API limit"):
        publish_image_pin(
            board_id="board-test",
            title="Valid title",
            description="x" * 801,
            alt_text="Valid alt text",
            image_url="https://example.com/image.png",
            affiliate_url="https://example.com/item",
        )
    assert calls == []


def test_final_workflow_pinterest_boundary_rejects_oversized_description(monkeypatch):
    from fastapi import HTTPException

    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def request(self, *args, **kwargs):
            calls.append(True)
            raise AssertionError("Pinterest network call must not occur")

    monkeypatch.setattr("app.workflow.httpx.Client", FakeClient)
    with pytest.raises(HTTPException) as error:
        _pinterest_request("POST", "/pins", "test-token", body={
            "title": "Valid title",
            "description": "x" * 801,
            "alt_text": "Valid alt text",
        })
    assert error.value.status_code == 422
    assert calls == []
