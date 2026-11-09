from __future__ import annotations

import pytest

from app import credential_vault, model2_repository
from psycopg.errors import UniqueViolation
from app.model2_domain import (
    AccountNicheAssignmentInput,
    AccountProfileInput,
    NicheInput,
)
from app.model2_repository import (
    Model2AccountNotConnectedError,
    Model2ConflictError,
    Model2NotFoundError,
)


class Cursor:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((" ".join(query.split()), params))
        response = self.responses.pop(0) if self.responses else None
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple) and response and response[0] == "many":
            return Cursor(many=response[1])
        return Cursor(one=response)


class ConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


def patch_connection(monkeypatch, conn):
    monkeypatch.setattr(model2_repository, "connection", lambda: ConnectionContext(conn))


def test_credential_metadata_check_reads_no_token_material():
    conn = FakeConnection([{"account_id": "pinterest:123456789", "pinterest_user_id": "123456789"}])

    assert credential_vault.pinterest_account_is_connected_in_transaction(
        conn, "pinterest:123456789"
    ) is True

    query, params = conn.calls[0]
    assert "SELECT account_id, pinterest_user_id" in query
    assert "status = 'connected'" in query
    assert "FOR SHARE" in query
    assert "ciphertext" not in query
    assert "token" not in query.lower()
    assert params == ("pinterest:123456789",)


def test_credential_metadata_check_rejects_mismatched_stored_pinterest_identity():
    conn = FakeConnection([{"account_id": "pinterest:123456789", "pinterest_user_id": "different-user"}])

    assert credential_vault.pinterest_account_is_connected_in_transaction(
        conn, "pinterest:123456789"
    ) is False
    query, _ = conn.calls[0]
    assert "pinterest_user_id" in query
    assert "ciphertext" not in query


def test_credential_metadata_check_returns_false_without_connected_row():
    conn = FakeConnection([None])

    assert credential_vault.pinterest_account_is_connected_in_transaction(
        conn, "pinterest:missing"
    ) is False


def test_save_account_profile_requires_connected_credential_on_onboarding(monkeypatch):
    conn = FakeConnection([
        None,  # profile row absent
        None,  # no connected credential
    ])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2AccountNotConnectedError):
        model2_repository.save_account_profile(
            AccountProfileInput(account_id="pinterest:123456789")
        )

    assert len(conn.calls) == 2
    assert "INSERT INTO model2_account_profiles" not in conn.calls[-1][0]


def test_save_account_profile_uses_metadata_only_check_and_returns_profile(monkeypatch):
    profile_row = {
        "account_id": "pinterest:123456789",
        "display_name": "Kitchen",
        "status": "active",
        "timezone": "Asia/Karachi",
    }
    conn = FakeConnection([None, {"account_id": "pinterest:123456789", "pinterest_user_id": "123456789"}, profile_row])
    patch_connection(monkeypatch, conn)

    result = model2_repository.save_account_profile(
        AccountProfileInput(
            account_id="pinterest:123456789",
            display_name=" Kitchen ",
            timezone="Asia/Karachi",
        )
    )

    assert result == profile_row
    assert "FOR SHARE" in conn.calls[1][0]
    assert "ciphertext" not in conn.calls[1][0]


def test_pausing_existing_profile_does_not_require_connected_token_and_pauses_mappings(monkeypatch):
    profile_row = {
        "account_id": "pinterest:123456789",
        "display_name": "Kitchen",
        "status": "paused",
        "timezone": "UTC",
    }
    conn = FakeConnection([
        {"account_id": "pinterest:123456789"},  # existing profile
        profile_row,  # update result
        None,  # pause active mappings
    ])
    patch_connection(monkeypatch, conn)

    result = model2_repository.save_account_profile(
        AccountProfileInput(account_id="pinterest:123456789", status="paused")
    )

    assert result["status"] == "paused"
    assert len(conn.calls) == 3
    assert "UPDATE model2_account_niches" in conn.calls[2][0]


def test_create_niche_reports_duplicate_slug(monkeypatch):
    conn = FakeConnection([None])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2ConflictError, match="slug already exists"):
        model2_repository.create_niche(
            NicheInput(slug="home-decor", display_name="Home Decor")
        )


def test_update_niche_archive_pauses_existing_assignments(monkeypatch):
    niche_row = {"id": 7, "slug": "home-decor", "status": "archived"}
    conn = FakeConnection([niche_row, None])
    patch_connection(monkeypatch, conn)

    result = model2_repository.update_niche(
        7,
        NicheInput(slug="home-decor", display_name="Home Decor", status="archived"),
    )

    assert result == niche_row
    assert "UPDATE model2_account_niches" in conn.calls[1][0]
    assert "WHERE niche_id = %s AND status = 'active'" in conn.calls[1][0]
    assert conn.calls[1][1] == (7,)


def test_update_niche_rejects_duplicate_slug(monkeypatch):
    conn = FakeConnection([UniqueViolation("duplicate slug")])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2ConflictError, match="slug already exists"):
        model2_repository.update_niche(
            7, NicheInput(slug="home-decor", display_name="Home Decor")
        )


def test_save_assignment_serializes_account_and_clears_previous_primary(monkeypatch):
    mapping_row = {
        "account_id": "pinterest:123456789",
        "niche_id": 9,
        "is_primary": True,
        "status": "active",
        "settings": {},
    }
    conn = FakeConnection([
        {"status": "active"},  # account profile FOR UPDATE
        {"status": "active"},  # niche FOR SHARE
        {"account_id": "pinterest:123456789", "pinterest_user_id": "123456789"},  # connected credential FOR SHARE
        None,  # clear previous active primary
        mapping_row,  # upsert target mapping
    ])
    patch_connection(monkeypatch, conn)

    result = model2_repository.save_account_niche_assignment(
        AccountNicheAssignmentInput(
            account_id="pinterest:123456789",
            niche_id=9,
            is_primary=True,
        )
    )

    assert result == mapping_row
    assert "FOR UPDATE" in conn.calls[0][0]
    assert "FOR SHARE" in conn.calls[1][0]
    assert "FOR SHARE" in conn.calls[2][0]
    assert "UPDATE model2_account_niches" in conn.calls[3][0]
    assert "niche_id <> %s" in conn.calls[3][0]


def test_save_assignment_rejects_missing_account_profile(monkeypatch):
    conn = FakeConnection([None])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2NotFoundError, match="Account profile"):
        model2_repository.save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id="pinterest:123456789",
                niche_id=9,
            )
        )


def test_save_assignment_rejects_active_mapping_for_paused_profile(monkeypatch):
    conn = FakeConnection([{"status": "paused"}, {"status": "active"}])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2ConflictError, match="paused account"):
        model2_repository.save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id="pinterest:123456789",
                niche_id=9,
                status="active",
            )
        )


def test_save_assignment_rejects_active_mapping_for_archived_niche(monkeypatch):
    conn = FakeConnection([
        {"status": "active"},
        {"status": "archived"},
    ])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2ConflictError, match="archived niche"):
        model2_repository.save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id="pinterest:123456789",
                niche_id=9,
                status="active",
            )
        )


def test_list_account_assignments_is_scoped_to_exact_account(monkeypatch):
    conn = FakeConnection([("many", [
        {"account_id": "pinterest:account-a", "niche_id": 1},
    ])])
    patch_connection(monkeypatch, conn)

    result = model2_repository.list_account_niche_assignments("pinterest:account-a")

    assert result == [{"account_id": "pinterest:account-a", "niche_id": 1}]
    query, params = conn.calls[0]
    assert "WHERE account_id = %s" in query
    assert params == ("pinterest:account-a",)


def test_save_assignment_requires_connected_credential_for_active_mapping(monkeypatch):
    conn = FakeConnection([
        {"status": "active"},
        {"status": "active"},
        None,
    ])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2AccountNotConnectedError):
        model2_repository.save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id="pinterest:123456789",
                niche_id=9,
                status="active",
            )
        )
    assert len(conn.calls) == 3
    assert "FOR SHARE" in conn.calls[2][0]


def test_get_active_niche_context_is_scoped_and_returns_only_approved_metadata(monkeypatch):
    context_row = {
        "account_status": "active",
        "assignment_status": "active",
        "niche_status": "active",
        "niche_id": 9,
        "slug": "home-decor",
        "display_name": "Home Decor",
        "description": "Storage and styling",
        "default_region": "US",
    }
    conn = FakeConnection([context_row])
    patch_connection(monkeypatch, conn)

    result = model2_repository.get_active_account_niche_context(
        "pinterest:123456789", 9
    )

    assert result == {
        "niche_id": 9,
        "slug": "home-decor",
        "display_name": "Home Decor",
        "description": "Storage and styling",
        "default_region": "US",
    }
    query, params = conn.calls[0]
    assert "WHERE ap.account_id = %s AND an.niche_id = %s" in query
    assert "FOR SHARE OF ap, an, n" in query
    assert params == ("pinterest:123456789", 9)


@pytest.mark.parametrize(
    "row",
    [
        {
            "account_status": "paused",
            "assignment_status": "active",
            "niche_status": "active",
        },
        {
            "account_status": "active",
            "assignment_status": "paused",
            "niche_status": "active",
        },
        {
            "account_status": "active",
            "assignment_status": "active",
            "niche_status": "archived",
        },
    ],
)
def test_get_active_niche_context_rejects_inactive_state(monkeypatch, row):
    conn = FakeConnection([row])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2ConflictError, match="must all be active"):
        model2_repository.get_active_account_niche_context(
            "pinterest:123456789", 9
        )


def test_get_active_niche_context_rejects_missing_mapping(monkeypatch):
    conn = FakeConnection([None])
    patch_connection(monkeypatch, conn)

    with pytest.raises(Model2NotFoundError, match="does not exist"):
        model2_repository.get_active_account_niche_context(
            "pinterest:123456789", 9
        )


def test_get_active_niche_context_rejects_invalid_niche_id(monkeypatch):
    conn = FakeConnection([])
    patch_connection(monkeypatch, conn)

    with pytest.raises(ValueError, match="positive integer"):
        model2_repository.get_active_account_niche_context(
            "pinterest:123456789", True
        )

    assert conn.calls == []
