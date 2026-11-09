"""Synthetic tests for versioned Pinterest token encryption and key rotation."""
import base64
import json

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app import credential_vault
from app.config import settings


def _encoded_key(byte):
    return base64.b64encode(bytes([byte]) * 32).decode("ascii")


def _use_keyring(monkeypatch, values, active):
    monkeypatch.setattr(settings, "pinterest_token_encryption_keys", json.dumps(values))
    monkeypatch.setattr(settings, "pinterest_token_encryption_active_key_id", active)


def test_versioned_envelope_records_key_id_and_round_trips(monkeypatch):
    _use_keyring(monkeypatch, {"k1": _encoded_key(1)}, "k1")
    blob = credential_vault._encrypt("synthetic-access-token", b"pinterest:123:access")
    assert blob.startswith(b"PVLT")
    assert blob[4] == 1
    assert blob[5] == 2
    assert blob[6:8] == b"k1"
    assert credential_vault._decrypt(blob, b"pinterest:123:access") == "synthetic-access-token"


def test_old_key_remains_readable_after_active_key_rotation(monkeypatch):
    _use_keyring(monkeypatch, {"old": _encoded_key(2)}, "old")
    old_blob = credential_vault._encrypt("old-token", b"account:access")
    _use_keyring(monkeypatch, {"old": _encoded_key(2), "new": _encoded_key(3)}, "new")
    new_blob = credential_vault._encrypt("new-token", b"account:access")
    assert old_blob[6:9] == b"old"
    assert new_blob[6:9] == b"new"
    assert credential_vault._decrypt(old_blob, b"account:access") == "old-token"
    assert credential_vault._decrypt(new_blob, b"account:access") == "new-token"


def test_legacy_nonce_ciphertext_remains_readable_during_migration(monkeypatch):
    key = bytes([4]) * 32
    nonce = bytes([5]) * 12
    aad = b"account:refresh"
    ciphertext = AESGCM(key).encrypt(nonce, b"legacy-refresh-token", aad)
    monkeypatch.setattr(settings, "pinterest_token_encryption_keys", None)
    monkeypatch.setattr(settings, "pinterest_token_encryption_active_key_id", None)
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", base64.b64encode(key).decode("ascii"))
    assert credential_vault._decrypt(nonce + ciphertext, aad) == "legacy-refresh-token"


def test_legacy_ciphertext_remains_readable_with_explicit_legacy_key_in_keyring(monkeypatch):
    key = bytes([6]) * 32
    nonce = bytes([7]) * 12
    aad = b"account:access"
    ciphertext = AESGCM(key).encrypt(nonce, b"legacy-access-token", aad)
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", None)
    _use_keyring(monkeypatch, {"legacy": base64.b64encode(key).decode("ascii"), "active": _encoded_key(8)}, "active")
    assert credential_vault._decrypt(nonce + ciphertext, aad) == "legacy-access-token"


def test_missing_old_key_fails_closed_for_old_versioned_envelope(monkeypatch):
    _use_keyring(monkeypatch, {"old": _encoded_key(9)}, "old")
    blob = credential_vault._encrypt("token", b"account:access")
    _use_keyring(monkeypatch, {"new": _encoded_key(10)}, "new")
    with pytest.raises(credential_vault.TokenEncryptionConfigurationError, match="key ID is not present"):
        credential_vault._decrypt(blob, b"account:access")


def test_wrong_key_does_not_return_plaintext(monkeypatch):
    _use_keyring(monkeypatch, {"k1": _encoded_key(11)}, "k1")
    blob = credential_vault._encrypt("synthetic-secret", b"account:access")
    _use_keyring(monkeypatch, {"k1": _encoded_key(12)}, "k1")
    with pytest.raises(InvalidTag):
        credential_vault._decrypt(blob, b"account:access")


def test_invalid_keyring_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_token_encryption_keys", "{bad-json")
    monkeypatch.setattr(settings, "pinterest_token_encryption_active_key_id", "k1")
    with pytest.raises(credential_vault.TokenEncryptionConfigurationError, match="JSON object"):
        credential_vault._encrypt("token", b"account:access")
