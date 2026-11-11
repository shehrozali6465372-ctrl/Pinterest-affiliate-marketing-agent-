"""Read-only Pinterest board verification; all provider traffic is mocked."""
import pytest

from app import pinterest


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def patch_client(monkeypatch, fake):
    monkeypatch.setattr(pinterest.httpx, "Client", lambda **_: fake)


def test_board_reader_follows_every_bookmark_and_only_uses_get(monkeypatch):
    fake = FakeClient([
        FakeResponse({"items": [{"id": "pin-1"}], "bookmark": "page-2"}),
        FakeResponse({"items": [{"id": "pin-2"}], "bookmark": None}),
    ])
    patch_client(monkeypatch, fake)

    result = pinterest.list_board_pins_read_only(board_id="board-1", access_token="test-token")

    assert result == {"items": [{"id": "pin-1"}, {"id": "pin-2"}], "pages_read": 2, "pagination_complete": True}
    assert len(fake.calls) == 2
    assert all(call[1].get("headers", {}).get("Authorization") == "Bearer test-token" for call in fake.calls)
    assert fake.calls[0][1]["params"] == {"page_size": 250}
    assert fake.calls[1][1]["params"] == {"page_size": 250, "bookmark": "page-2"}


def test_board_reader_fails_closed_on_repeated_bookmark(monkeypatch):
    fake = FakeClient([
        FakeResponse({"items": [], "bookmark": "same"}),
        FakeResponse({"items": [], "bookmark": "same"}),
    ])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="repeated"):
        pinterest.list_board_pins_read_only(board_id="board-1", access_token="test-token")


def test_board_reader_does_not_claim_complete_when_page_cap_reached(monkeypatch):
    fake = FakeClient([FakeResponse({"items": [], "bookmark": "next"})])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="safety limit"):
        pinterest.list_board_pins_read_only(board_id="board-1", access_token="test-token", max_pages=1)


def test_board_reader_rejects_provider_error_without_exposing_body(monkeypatch):
    fake = FakeClient([FakeResponse({"message": "sensitive provider detail"}, status_code=403)])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="HTTP 403") as error:
        pinterest.list_board_pins_read_only(board_id="board-1", access_token="test-token")
    assert "sensitive provider detail" not in str(error.value)


def test_pin_detail_reader_uses_get_and_returns_json(monkeypatch):
    fake = FakeClient([FakeResponse({"id": "pin-1", "board_id": "board-1"})])
    patch_client(monkeypatch, fake)
    result = pinterest.get_pin_read_only(pin_id="pin-1", access_token="test-token")
    assert result == {"id": "pin-1", "board_id": "board-1"}
    assert fake.calls[0][0].endswith("/pins/pin-1")


def test_board_list_reader_follows_every_bookmark_and_uses_get_only(monkeypatch):
    fake = FakeClient([
        FakeResponse({"items": [{"id": "board-1", "name": "Kitchen"}], "bookmark": "next-page"}),
        FakeResponse({"items": [{"id": "board-2", "name": "Decor"}], "bookmark": None}),
    ])
    patch_client(monkeypatch, fake)

    result = pinterest.list_boards_read_only(access_token="test-token")

    assert result == {
        "items": [
            {"id": "board-1", "name": "Kitchen"},
            {"id": "board-2", "name": "Decor"},
        ],
        "pages_read": 2,
        "pagination_complete": True,
    }
    assert len(fake.calls) == 2
    assert all(call[1].get("headers", {}).get("Authorization") == "Bearer test-token" for call in fake.calls)
    assert all(call[0].endswith("/boards") for call in fake.calls)
    assert fake.calls[0][1]["params"] == {"page_size": 100}
    assert fake.calls[1][1]["params"] == {"page_size": 100, "bookmark": "next-page"}


def test_board_list_reader_rejects_repeated_bookmark(monkeypatch):
    fake = FakeClient([
        FakeResponse({"items": [], "bookmark": "same"}),
        FakeResponse({"items": [], "bookmark": "same"}),
    ])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="repeated"):
        pinterest.list_boards_read_only(access_token="test-token")


def test_board_list_reader_rejects_incomplete_pagination(monkeypatch):
    fake = FakeClient([FakeResponse({"items": [{"id": "board-1", "name": "Kitchen"}], "bookmark": "next"})])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="safety limit"):
        pinterest.list_boards_read_only(access_token="test-token", max_pages=1)


def test_board_list_reader_rejects_invalid_board_record(monkeypatch):
    fake = FakeClient([FakeResponse({"items": [{"name": "Missing ID"}], "bookmark": None})])
    patch_client(monkeypatch, fake)
    with pytest.raises(pinterest.PinterestReadError, match="invalid board record"):
        pinterest.list_boards_read_only(access_token="test-token")


def test_board_resolver_requires_one_case_insensitive_exact_match(monkeypatch):
    monkeypatch.setattr(pinterest, "list_boards_read_only", lambda **_: {
        "items": [
            {"id": "board-1", "name": "Kitchen Finds"},
            {"id": "board-2", "name": "Kitchen Finds 2026"},
        ],
        "pages_read": 2,
        "pagination_complete": True,
    })

    result = pinterest.resolve_board_id_read_only(
        board_name="kitchen finds", access_token="test-token",
    )

    assert result == {
        "board_id": "board-1",
        "board_name": "Kitchen Finds",
        "pages_read": 2,
        "pagination_complete": True,
    }


def test_board_resolver_rejects_missing_and_duplicate_exact_matches(monkeypatch):
    listing = {"items": [{"id": "board-1", "name": "Kitchen"}], "pages_read": 1, "pagination_complete": True}
    monkeypatch.setattr(pinterest, "list_boards_read_only", lambda **_: listing)
    with pytest.raises(pinterest.PinterestReadError, match="No exact-name"):
        pinterest.resolve_board_id_read_only(board_name="Decor", access_token="test-token")

    duplicate = {
        "items": [
            {"id": "board-1", "name": "Kitchen"},
            {"id": "board-2", "name": "kitchen"},
        ],
        "pages_read": 1,
        "pagination_complete": True,
    }
    monkeypatch.setattr(pinterest, "list_boards_read_only", lambda **_: duplicate)
    with pytest.raises(pinterest.PinterestReadError, match="ambiguous"):
        pinterest.resolve_board_id_read_only(board_name="Kitchen", access_token="test-token")
