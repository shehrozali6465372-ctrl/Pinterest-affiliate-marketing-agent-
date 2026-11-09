from datetime import datetime, timedelta, timezone

import pytest

from app import credential_vault


def test_read_only_credential_returns_valid_token_without_oauth_refresh(monkeypatch):
    expected = {
        "account_id": "pinterest:test-account",
        "access_token": "test-token-never-log",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    monkeypatch.setattr(credential_vault, "_read_access_credential", lambda account_id: expected)

    def forbidden_refresh(account_id):
        raise AssertionError("read-only credential lookup must never refresh OAuth")

    monkeypatch.setattr(credential_vault, "_refresh_access_token", forbidden_refresh)

    result = credential_vault.get_pinterest_credential_read_only("pinterest:test-account")

    assert result is expected
    assert result["access_token"] == "test-token-never-log"


@pytest.mark.parametrize(
    "expires_at",
    [None, datetime.now(timezone.utc) - timedelta(seconds=1), datetime.now(timezone.utc) + timedelta(minutes=4)],
)
def test_read_only_credential_fails_closed_without_refresh_for_expired_or_unknown_expiry(monkeypatch, expires_at):
    monkeypatch.setattr(
        credential_vault,
        "_read_access_credential",
        lambda account_id: {"account_id": account_id, "access_token": "test-token", "expires_at": expires_at},
    )

    def forbidden_refresh(account_id):
        raise AssertionError("read-only credential lookup must never refresh OAuth")

    monkeypatch.setattr(credential_vault, "_refresh_access_token", forbidden_refresh)

    with pytest.raises(RuntimeError, match="read-only operation will not refresh"):
        credential_vault.get_pinterest_credential_read_only("pinterest:test-account")
