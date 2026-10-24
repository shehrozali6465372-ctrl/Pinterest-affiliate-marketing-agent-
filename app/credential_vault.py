"""Encrypted at-rest storage for OAuth credentials received server-to-server."""
from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings
from app.database import connection


def _cipher() -> AESGCM:
    encoded = settings.pinterest_token_encryption_key
    if not encoded:
        raise RuntimeError("PINTEREST_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise RuntimeError("PINTEREST_TOKEN_ENCRYPTION_KEY must be base64-encoded 32-byte key") from exc
    if len(key) != 32:
        raise RuntimeError("PINTEREST_TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return AESGCM(key)


def _encrypt(cipher: AESGCM, value: str, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + cipher.encrypt(nonce, value.encode("utf-8"), aad)


def store_pinterest_credential(payload: dict[str, Any]) -> dict[str, Any]:
    """Encrypt token material before it reaches PostgreSQL; never return token fields."""
    cipher = _cipher()
    account_id = str(payload["account_id"])
    user_id = str(payload["pinterest_user_id"])
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
