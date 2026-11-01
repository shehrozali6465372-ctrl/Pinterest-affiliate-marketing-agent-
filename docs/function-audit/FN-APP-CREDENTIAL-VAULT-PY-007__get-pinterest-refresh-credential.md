# get_pinterest_refresh_credential

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-007`
- **Source:** `app/credential_vault.py:102-125`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Retrieves and decrypts the refresh-token credential for an account. Verify token purpose separation, null/missing refresh-token behavior, AAD consistency and that access tokens are not accidentally returned as refresh tokens.

## Exact isolated source

```python
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the source blob.
- `VERIFIED — DEFINITION RANGE`: isolated to one definition.
- `UNVERIFIED — CRYPTOGRAPHIC CORRECTNESS`: key, nonce, AAD, decrypt compatibility and tests require proof.
- `UNVERIFIED — PRODUCTION CREDENTIAL STATE`: no live credential was accessed or changed.

## Required checks

Trace every caller and raise site; inspect unit tests for malformed keys, nonce uniqueness, encryption/decryption round trips, account isolation, token rotation and revocation. Do not inspect or expose actual production secrets.
