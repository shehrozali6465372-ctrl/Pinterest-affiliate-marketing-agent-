"""The canonical publisher validates all text before ledger reservation or network I/O."""

import pytest
from fastapi import HTTPException

from app.publishing_gateway import publish_pin


def test_canonical_gateway_rejects_oversized_text_before_reserving_or_posting(monkeypatch):
    import app.database as database
    import app.publishing_gateway as gateway

    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: pytest.fail("ledger must not be reserved"))
    monkeypatch.setattr(gateway.httpx, "Client", lambda **kwargs: pytest.fail("Pinterest must not be called"))
    with pytest.raises(HTTPException) as error:
        publish_pin(
            product_id=1, content_version_id=1, board_id="board-1",
            account_id="pinterest:account-1", access_token="test-token",
            title="Valid title", description="x" * 801, alt_text="Valid alt",
            media_source={"source_type": "image_url", "url": "https://example.test/image.png"},
            destination_url="https://example.test/item",
        )
    assert error.value.status_code == 422
    assert "800-character API limit" in error.value.detail


def test_canonical_gateway_rejects_missing_account_before_reserving(monkeypatch):
    import app.database as database
    monkeypatch.setattr(database, "begin_publish_attempt", lambda **kwargs: pytest.fail("ledger must not be reserved"))
    with pytest.raises(HTTPException) as error:
        publish_pin(
            product_id=1, content_version_id=1, board_id="board-1",
            account_id=None, access_token="test-token",
            title="Valid title", description="Valid description", alt_text="Valid alt",
            media_source={"source_type": "image_url", "url": "https://example.test/image.png"},
            destination_url="https://example.test/item",
        )
    assert error.value.status_code == 422
