import pytest
from pydantic import ValidationError

from app.content_generation import AFFILIATE_DISCLOSURE, GeneratedContent, _with_affiliate_disclosure
from app.pin_limits import PIN_ALT_TEXT_MAX_LENGTH, PIN_DESCRIPTION_MAX_LENGTH, PIN_TITLE_MAX_LENGTH
from app.workflow import _pinterest_request


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


def test_workflow_helper_blocks_direct_pin_write_bypass():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        _pinterest_request("POST", "/pins", "test-token", body={"title": "Valid"})
    assert error.value.status_code == 400
    assert "canonical publication-ledger gateway" in error.value.detail
