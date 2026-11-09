"""Credential vault account identity invariants."""
import pytest

from app import credential_vault


def test_credential_identity_accepts_exact_canonical_account_id():
    credential_vault._validate_account_identity("pinterest:123456", "123456")


@pytest.mark.parametrize(
    ("account_id", "pinterest_user_id"),
    [
        ("pinterest:other-user", "123456"),
        ("123456", "123456"),
        ("pinterest:", ""),
        ("pinterest:123456:extra", "123456"),
    ],
)
def test_credential_identity_rejects_mismatched_or_noncanonical_account_id(
    account_id, pinterest_user_id
):
    with pytest.raises(ValueError, match="account_id must match pinterest_user_id"):
        credential_vault._validate_account_identity(account_id, pinterest_user_id)


def test_mismatched_credential_is_rejected_before_encryption_or_database_write(monkeypatch):
    monkeypatch.setattr(credential_vault.settings, "pinterest_token_encryption_key", None)

    def unexpected_database_access():
        raise AssertionError("database must not be touched for mismatched identity")

    monkeypatch.setattr(credential_vault, "connection", unexpected_database_access)
    with pytest.raises(ValueError, match="account_id must match pinterest_user_id"):
        credential_vault.store_pinterest_credential(
            {
                "account_id": "pinterest:attacker-selected",
                "pinterest_user_id": "actual-user",
                "access_token": "synthetic-access-token",
                "refresh_token": "synthetic-refresh-token",
            }
        )
