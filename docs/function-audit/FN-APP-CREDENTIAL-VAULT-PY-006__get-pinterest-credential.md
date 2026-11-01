# get_pinterest_credential

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-006`
- **Source:** `app/credential_vault.py:85-101`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Loads a stored account credential and decrypts access token material. Verify ciphertext/nonce/AAD compatibility, account scoping, revoked/expired credential handling and that refresh token data is not exposed unnecessarily.

## Exact isolated source

```python
def get_pinterest_credential(account_id: str) -> dict[str, Any]:
    """Decrypt a connected account token only in process memory for a server-side API call."""
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
    blob = bytes(row["access_token_ciphertext"])
    token = cipher.decrypt(blob[:12], blob[12:], f"{account_id}:access".encode()).decode("utf-8")
    return {"account_id": row["account_id"], "pinterest_user_id": row["pinterest_user_id"], "username": row["username"], "access_token": token, "token_type": row["token_type"], "scope": row["scope"], "expires_at": row["expires_at"]}


```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source blob.
- `VERIFIED — LINE RANGE`: source lines isolated as a single definition.
- `UNVERIFIED — LOGIC`: caller/callee, tests, concurrency and failure behavior remain to be proven.
- `UNVERIFIED — LIVE DATABASE`: no production DB writes or state transitions executed.

## Remaining evidence

Review all call sites, SQL schema/migrations, transaction boundaries, integration tests, race-condition tests, failure injection and production logs without changing data.
