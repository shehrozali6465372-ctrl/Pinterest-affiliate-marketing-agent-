"""Encrypted at-rest storage for OAuth credentials received server-to-server."""
from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings
from app.database import connection


class TokenEncryptionConfigurationError(RuntimeError):
    """Raised only when the token-encryption key is missing or invalid."""


def _validate_account_identity(account_id: str, pinterest_user_id: str) -> None:
    """Reject credential rows whose canonical account key disagrees with Pinterest identity."""
    if (
        not pinterest_user_id
        or any(character.isspace() for character in pinterest_user_id)
        or ":" in pinterest_user_id
        or account_id != f"pinterest:{pinterest_user_id}"
    ):
        raise ValueError("Pinterest account_id must match pinterest_user_id")


_ENVELOPE_MAGIC = b"PVLT"
_ENVELOPE_VERSION = 1
_MAX_KEY_ID_BYTES = 64


def _decode_key(encoded: object, label: str) -> AESGCM:
    if not isinstance(encoded, str) or not encoded:
        raise TokenEncryptionConfigurationError(f"{label} is missing")
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception:
        raise TokenEncryptionConfigurationError(f"{label} must be base64-encoded") from None
    if len(key) != 32:
        raise TokenEncryptionConfigurationError(f"{label} must decode to exactly 32 bytes")
    return AESGCM(key)


def _keyring() -> tuple[str, dict[str, AESGCM]]:
    import json
    import re
    raw_ring = settings.pinterest_token_encryption_keys
    if raw_ring:
        try:
            values = json.loads(raw_ring)
        except (TypeError, ValueError):
            raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEYS must be a JSON object") from None
        if not isinstance(values, dict) or not values:
            raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEYS must be a non-empty JSON object")
        keys: dict[str, AESGCM] = {}
        for key_id, encoded in values.items():
            if not isinstance(key_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", key_id):
                raise TokenEncryptionConfigurationError("Encryption key IDs must be 1-64 safe ASCII characters")
            keys[key_id] = _decode_key(encoded, f"Encryption key '{key_id}'")
        active_id = settings.pinterest_token_encryption_active_key_id
        if not active_id or active_id not in keys:
            raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_ACTIVE_KEY_ID must identify a configured key")
        return active_id, keys
    return "legacy", {"legacy": _decode_key(settings.pinterest_token_encryption_key, "PINTEREST_TOKEN_ENCRYPTION_KEY")}


def token_encryption_key_is_valid() -> bool:
    try:
        _keyring()
    except TokenEncryptionConfigurationError:
        return False
    return True


def _encrypt(value: str, aad: bytes) -> bytes:
    active_id, keys = _keyring()
    key_id = active_id.encode("ascii")
    nonce = os.urandom(12)
    encrypted = keys[active_id].encrypt(nonce, value.encode("utf-8"), aad)
    return _ENVELOPE_MAGIC + bytes((_ENVELOPE_VERSION, len(key_id))) + key_id + nonce + encrypted


def _decrypt(blob: bytes, aad: bytes) -> str:
    if blob.startswith(_ENVELOPE_MAGIC):
        if len(blob) < 6:
            raise TokenEncryptionConfigurationError("Encrypted credential envelope is truncated")
        version, key_id_length = blob[4], blob[5]
        if version != _ENVELOPE_VERSION or not 1 <= key_id_length <= _MAX_KEY_ID_BYTES:
            raise TokenEncryptionConfigurationError("Encrypted credential envelope version or key ID is unsupported")
        end = 6 + key_id_length
        if len(blob) < end + 28:
            raise TokenEncryptionConfigurationError("Encrypted credential envelope is truncated")
        try:
            key_id = blob[6:end].decode("ascii")
        except UnicodeDecodeError:
            raise TokenEncryptionConfigurationError("Encrypted credential envelope key ID is invalid") from None
        _, keys = _keyring()
        cipher = keys.get(key_id)
        if cipher is None:
            raise TokenEncryptionConfigurationError("Encrypted credential key ID is not present in the configured keyring")
        return cipher.decrypt(blob[end:end + 12], blob[end + 12:], aad).decode("utf-8")
    if settings.pinterest_token_encryption_keys:
        _, keys = _keyring()
        cipher = keys.get("legacy")
        if cipher is None and settings.pinterest_token_encryption_key:
            cipher = _decode_key(settings.pinterest_token_encryption_key, "PINTEREST_TOKEN_ENCRYPTION_KEY")
    else:
        cipher = _decode_key(settings.pinterest_token_encryption_key, "PINTEREST_TOKEN_ENCRYPTION_KEY")
    if cipher is None:
        raise TokenEncryptionConfigurationError("Legacy Pinterest credentials require the original encryption key")
    if len(blob) < 28:
        raise TokenEncryptionConfigurationError("Legacy encrypted credential is truncated")
    return cipher.decrypt(blob[:12], blob[12:], aad).decode("utf-8")

def store_pinterest_credential(payload: dict[str, Any]) -> dict[str, Any]:
    """Encrypt token material before it reaches PostgreSQL; never return token fields."""
    account_id = str(payload["account_id"])
    user_id = str(payload["pinterest_user_id"])
    _validate_account_identity(account_id, user_id)
    access = str(payload["access_token"])
    refresh = str(payload.get("refresh_token") or "")
    access_blob = _encrypt(access, f"{account_id}:access".encode())
    refresh_blob = _encrypt(refresh, f"{account_id}:refresh".encode()) if refresh else None
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO pinterest_credentials
                (account_id, pinterest_user_id, username, access_token_ciphertext,
                 refresh_token_ciphertext, token_type, scope, expires_at,
                 refresh_token_expires_at, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'connected', now())
            ON CONFLICT (account_id) DO UPDATE SET
                pinterest_user_id = EXCLUDED.pinterest_user_id,
                username = EXCLUDED.username,
                access_token_ciphertext = EXCLUDED.access_token_ciphertext,
                refresh_token_ciphertext = COALESCE(EXCLUDED.refresh_token_ciphertext, pinterest_credentials.refresh_token_ciphertext),
                token_type = EXCLUDED.token_type,
                scope = EXCLUDED.scope,
                expires_at = EXCLUDED.expires_at,
                refresh_token_expires_at = COALESCE(EXCLUDED.refresh_token_expires_at, pinterest_credentials.refresh_token_expires_at),
                status = 'connected',
                updated_at = now()
            RETURNING account_id, pinterest_user_id, username, status, updated_at
            """,
            (
                account_id, user_id, str(payload.get("username") or ""),
                access_blob, refresh_blob, str(payload.get("token_type") or "bearer"),
                str(payload.get("scope") or ""),
                payload.get("expires_at"), payload.get("refresh_token_expires_at"),
            ),
        ).fetchone()
        return dict(row)


def _read_access_credential(account_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            """SELECT account_id, pinterest_user_id, username, access_token_ciphertext,
                      token_type, scope, expires_at, status
               FROM pinterest_credentials WHERE account_id = %s""",
            (account_id,),
        ).fetchone()
    if not row or row["status"] != "connected":
        raise LookupError("Pinterest account is not connected")
    _validate_account_identity(str(row["account_id"]), str(row["pinterest_user_id"]))
    blob = bytes(row["access_token_ciphertext"])
    token = _decrypt(blob, f"{account_id}:access".encode())
    return {"account_id": row["account_id"], "pinterest_user_id": row["pinterest_user_id"], "username": row["username"], "access_token": token, "token_type": row["token_type"], "scope": row["scope"], "expires_at": row["expires_at"]}


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _refresh_access_token(account_id: str) -> None:
    """Refresh under a per-account PostgreSQL advisory lock to prevent token-rotation races."""
    from datetime import datetime, timedelta, timezone
    import httpx

    if not settings.pinterest_client_id or not settings.pinterest_client_secret:
        raise RuntimeError("Pinterest OAuth app credentials are not configured for automatic token refresh")

    # The transaction-scoped lock remains held across provider refresh and encrypted persistence.
    with connection() as lock_conn:
        lock_conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"pinterest-token-refresh:{account_id}",))
        current = _read_access_credential(account_id)
        expiry = _as_utc(current.get("expires_at"))
        if expiry is None or expiry > datetime.now(timezone.utc) + timedelta(minutes=5):
            return

        stored = get_pinterest_refresh_credential(account_id)
        refresh_expiry = _as_utc(stored.get("refresh_token_expires_at"))
        if stored.get("refresh_token_expires_at") is not None and (refresh_expiry is None or refresh_expiry <= datetime.now(timezone.utc)):
            raise LookupError("Pinterest refresh token has expired; reconnect the account")

        try:
            with httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
                response = client.post(
                    f"{settings.pinterest_api_base_url.rstrip('/')}/oauth/token",
                    auth=(settings.pinterest_client_id, settings.pinterest_client_secret),
                    data={"grant_type": "refresh_token", "refresh_token": stored["refresh_token"], "continuous_refresh": "true"},
                )
            data = response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            raise RuntimeError("Pinterest access-token refresh request failed") from None
        if not response.is_success or not isinstance(data, dict) or not data.get("access_token"):
            raise RuntimeError("Pinterest rejected access-token refresh; reconnect if the refresh token is invalid")

        now = datetime.now(timezone.utc)
        try:
            expires_at = (now + timedelta(seconds=int(data["expires_in"]))).isoformat() if data.get("expires_in") is not None else None
            if expires_at is None:
                raise ValueError("expires_in missing")
        except (TypeError, ValueError, OverflowError):
            raise RuntimeError("Pinterest refresh response did not contain a valid access-token expiry") from None

        if data.get("refresh_token_expires_at") is not None:
            try:
                new_refresh_expiry = datetime.fromtimestamp(float(data["refresh_token_expires_at"]), timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                raise RuntimeError("Pinterest returned an invalid refresh-token expiry") from None
        elif data.get("refresh_token_expires_in") is not None:
            try:
                new_refresh_expiry = (now + timedelta(seconds=int(data["refresh_token_expires_in"]))).isoformat()
            except (TypeError, ValueError, OverflowError):
                raise RuntimeError("Pinterest returned an invalid refresh-token lifetime") from None
        else:
            new_refresh_expiry = stored.get("refresh_token_expires_at")

        store_pinterest_credential({
            "account_id": stored["account_id"],
            "pinterest_user_id": stored["pinterest_user_id"],
            "username": stored.get("username") or "",
            "access_token": str(data["access_token"]),
            "refresh_token": str(data.get("refresh_token") or stored["refresh_token"]),
            "token_type": str(data.get("token_type") or "bearer"),
            "scope": str(data.get("scope") or stored.get("scope") or ""),
            "expires_at": expires_at,
            "refresh_token_expires_at": new_refresh_expiry,
        })


def get_pinterest_credential(account_id: str) -> dict[str, Any]:
    """Return a valid access token, refreshing it before expiry when server credentials exist."""
    current = _read_access_credential(account_id)
    expiry = _as_utc(current.get("expires_at"))
    from datetime import datetime, timedelta, timezone
    if expiry is not None and expiry <= datetime.now(timezone.utc) + timedelta(minutes=5):
        _refresh_access_token(account_id)
        current = _read_access_credential(account_id)
        refreshed_expiry = _as_utc(current.get("expires_at"))
        if refreshed_expiry is not None and refreshed_expiry <= datetime.now(timezone.utc):
            raise RuntimeError("Pinterest access token remains expired after refresh")
    return current


def get_pinterest_refresh_credential(account_id: str) -> dict[str, Any]:
    """Decrypt the refresh token only for a trusted server-side token refresh."""
    with connection() as conn:
        row = conn.execute(
            """SELECT account_id, pinterest_user_id, username, refresh_token_ciphertext,
                      scope, refresh_token_expires_at, status
               FROM pinterest_credentials WHERE account_id = %s""",
            (account_id,),
        ).fetchone()
    if not row or row["status"] != "connected" or not row["refresh_token_ciphertext"]:
        raise LookupError("Pinterest refresh credential is not available")
    _validate_account_identity(str(row["account_id"]), str(row["pinterest_user_id"]))
    blob = bytes(row["refresh_token_ciphertext"])
    refresh_token = _decrypt(blob, f"{account_id}:refresh".encode())
    return {
        "account_id": row["account_id"],
        "pinterest_user_id": row["pinterest_user_id"],
        "username": row["username"],
        "refresh_token": refresh_token,
        "scope": row["scope"],
        "refresh_token_expires_at": row["refresh_token_expires_at"],
    }




def _ciphertext_key_id(blob: bytes | memoryview | None) -> str:
    """Return an envelope key ID without decrypting or exposing token material."""
    import re

    if blob is None:
        return "absent"
    raw = bytes(blob)
    if raw.startswith(_ENVELOPE_MAGIC):
        if len(raw) < 6:
            return "invalid"
        version, key_id_length = raw[4], raw[5]
        if version != _ENVELOPE_VERSION or not 1 <= key_id_length <= _MAX_KEY_ID_BYTES:
            return "invalid"
        end = 6 + key_id_length
        if len(raw) < end + 28:
            return "invalid"
        try:
            key_id = raw[6:end].decode("ascii")
        except UnicodeDecodeError:
            return "invalid"
        return key_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", key_id) else "invalid"
    return "legacy" if len(raw) >= 28 else "invalid"


def pinterest_credential_encryption_inventory() -> dict[str, Any]:
    """Return aggregate ciphertext key-ID counts across all credential statuses.

    This is read-only metadata inspection. It includes revoked rows and never
    decrypts, returns, or logs token material or account identifiers.
    """
    with connection() as conn:
        rows = conn.execute(
            """SELECT account_id, pinterest_user_id, status,
                      access_token_ciphertext, refresh_token_ciphertext
               FROM pinterest_credentials ORDER BY account_id"""
        ).fetchall()

    access_counts: dict[str, int] = {}
    refresh_counts: dict[str, int] = {}
    invalid_identity_rows = 0
    for row in rows:
        try:
            _validate_account_identity(str(row["account_id"]), str(row["pinterest_user_id"]))
        except (KeyError, TypeError, ValueError):
            invalid_identity_rows += 1
        access_id = _ciphertext_key_id(row.get("access_token_ciphertext"))
        refresh_id = _ciphertext_key_id(row.get("refresh_token_ciphertext"))
        access_counts[access_id] = access_counts.get(access_id, 0) + 1
        refresh_counts[refresh_id] = refresh_counts.get(refresh_id, 0) + 1

    return {
        "credential_rows": len(rows),
        "invalid_identity_rows": invalid_identity_rows,
        "access_token_key_ids": dict(sorted(access_counts.items())),
        "refresh_token_key_ids": dict(sorted(refresh_counts.items())),
        "includes_revoked_rows": True,
        "tokens_decrypted": False,
    }


def reencrypt_pinterest_credential(account_id: str) -> dict[str, Any]:
    """Re-encrypt one stored credential under the active key; never calls Pinterest.

    This is an operator-invoked maintenance primitive, not an HTTP endpoint.
    Keep all old key IDs configured until every stored row has been migrated
    and independently verified.
    """
    active_id, _ = _keyring()
    with connection() as conn:
        row = conn.execute(
            """SELECT account_id, pinterest_user_id, access_token_ciphertext,
                      refresh_token_ciphertext
               FROM pinterest_credentials WHERE account_id = %s FOR UPDATE""",
            (account_id,),
        ).fetchone()
        if not row:
            raise LookupError("Pinterest account credential is not available")
        stored_account_id = str(row["account_id"])
        user_id = str(row["pinterest_user_id"])
        _validate_account_identity(stored_account_id, user_id)
        access = _decrypt(bytes(row["access_token_ciphertext"]), f"{stored_account_id}:access".encode())
        refresh_blob = row["refresh_token_ciphertext"]
        refresh = (
            _decrypt(bytes(refresh_blob), f"{stored_account_id}:refresh".encode())
            if refresh_blob is not None
            else None
        )
        new_access = _encrypt(access, f"{stored_account_id}:access".encode())
        new_refresh = (
            _encrypt(refresh, f"{stored_account_id}:refresh".encode())
            if refresh is not None
            else None
        )
        if new_refresh is None:
            conn.execute(
                """UPDATE pinterest_credentials
                   SET access_token_ciphertext = %s, updated_at = now()
                   WHERE account_id = %s""",
                (new_access, stored_account_id),
            )
        else:
            conn.execute(
                """UPDATE pinterest_credentials
                   SET access_token_ciphertext = %s,
                       refresh_token_ciphertext = %s,
                       updated_at = now()
                   WHERE account_id = %s""",
                (new_access, new_refresh, stored_account_id),
            )
    return {
        "account_id": stored_account_id,
        "re_encrypted": True,
        "active_key_id": active_id,
        "refresh_token_re_encrypted": refresh is not None,
        "pinterest_api_called": False,
    }

def revoke_pinterest_credential(account_id: str) -> None:
    """Disable a credential only after validating its stored canonical Pinterest identity."""
    with connection() as conn:
        row = conn.execute(
            "SELECT account_id, pinterest_user_id FROM pinterest_credentials WHERE account_id = %s FOR UPDATE",
            (account_id,),
        ).fetchone()
        if not row:
            raise LookupError("Pinterest account is not connected")
        _validate_account_identity(str(row["account_id"]), str(row["pinterest_user_id"]))
        conn.execute(
            "UPDATE pinterest_credentials SET status = 'revoked', updated_at = now() WHERE account_id = %s",
            (account_id,),
        )


def pinterest_account_is_connected_in_transaction(conn, account_id: str) -> bool:
    """Check connection state using metadata only inside the caller's transaction.

    This intentionally does not instantiate the cipher, read ciphertext, decrypt
    tokens, or invoke OAuth refresh. FOR SHARE keeps the connected-state row stable
    until the caller's transaction commits or rolls back.
    """
    row = conn.execute(
        """
        SELECT account_id, pinterest_user_id
        FROM pinterest_credentials
        WHERE account_id = %s AND status = 'connected'
        FOR SHARE
        """,
        (account_id,),
    ).fetchone()
    if row is None:
        return False
    try:
        _validate_account_identity(str(row["account_id"]), str(row["pinterest_user_id"]))
    except (KeyError, TypeError, ValueError):
        return False
    return True
