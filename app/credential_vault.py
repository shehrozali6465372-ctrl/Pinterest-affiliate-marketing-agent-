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


def _cipher() -> AESGCM:
    encoded = settings.pinterest_token_encryption_key
    if not encoded:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY must be base64-encoded 32-byte key") from exc
    if len(key) != 32:
        raise TokenEncryptionConfigurationError("PINTEREST_TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return AESGCM(key)


def token_encryption_key_is_valid() -> bool:
    """Validate the configured AES-256-GCM key format without reading or exposing secret material."""
    try:
        _cipher()
    except TokenEncryptionConfigurationError:
        return False
    return True


def _encrypt(cipher: AESGCM, value: str, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + cipher.encrypt(nonce, value.encode("utf-8"), aad)


def store_pinterest_credential(payload: dict[str, Any]) -> dict[str, Any]:
    """Encrypt token material before it reaches PostgreSQL; never return token fields."""
    account_id = str(payload["account_id"])
    user_id = str(payload["pinterest_user_id"])
    _validate_account_identity(account_id, user_id)
    cipher = _cipher()
    access = str(payload["access_token"])
    refresh = str(payload.get("refresh_token") or "")
    access_blob = _encrypt(cipher, access, f"{account_id}:access".encode())
    refresh_blob = _encrypt(cipher, refresh, f"{account_id}:refresh".encode()) if refresh else None
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
    cipher = _cipher()
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
    token = cipher.decrypt(blob[:12], blob[12:], f"{account_id}:access".encode()).decode("utf-8")
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
    cipher = _cipher()
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
    refresh_token = cipher.decrypt(blob[:12], blob[12:], f"{account_id}:refresh".encode()).decode("utf-8")
    return {
        "account_id": row["account_id"],
        "pinterest_user_id": row["pinterest_user_id"],
        "username": row["username"],
        "refresh_token": refresh_token,
        "scope": row["scope"],
        "refresh_token_expires_at": row["refresh_token_expires_at"],
    }


def revoke_pinterest_credential(account_id: str) -> None:
    """Disable an account in the Agent database without exposing its token."""
    with connection() as conn:
        conn.execute("UPDATE pinterest_credentials SET status = 'revoked', updated_at = now() WHERE account_id = %s", (account_id,))


def pinterest_account_is_connected_in_transaction(conn, account_id: str) -> bool:
    """Check connection state using metadata only inside the caller's transaction.

    This intentionally does not instantiate the cipher, read ciphertext, decrypt
    tokens, or invoke OAuth refresh. FOR SHARE keeps the connected-state row stable
    until the caller's transaction commits or rolls back.
    """
    row = conn.execute(
        """
        SELECT account_id
        FROM pinterest_credentials
        WHERE account_id = %s AND status = 'connected'
        FOR SHARE
        """,
        (account_id,),
    ).fetchone()
    return row is not None
