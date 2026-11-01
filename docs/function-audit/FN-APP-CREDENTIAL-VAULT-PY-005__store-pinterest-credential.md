# store_pinterest_credential

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-005`
- **Source:** `app/credential_vault.py:45-84`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This record isolates one definition. Review the source line by line, its direct callers, callees, tests and side effects before marking its behavior verified.

## Source excerpt

```python
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


```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
