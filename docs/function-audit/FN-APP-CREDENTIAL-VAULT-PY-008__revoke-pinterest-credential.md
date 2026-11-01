# revoke_pinterest_credential

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-008`
- **Source:** `app/credential_vault.py:126-130`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Revokes/deletes stored Pinterest credential material. Verify whether this is a hard delete or status update, cascade implications, idempotent behavior and that revocation does not leak plaintext token values.

## Exact isolated source

```python
def revoke_pinterest_credential(account_id: str) -> None:
    """Disable an account in the Agent database without exposing its token."""
    with connection() as conn:
        conn.execute("UPDATE pinterest_credentials SET status = 'revoked', updated_at = now() WHERE account_id = %s", (account_id,))
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the source blob.
- `VERIFIED — DEFINITION RANGE`: isolated to one definition.
- `UNVERIFIED — CRYPTOGRAPHIC CORRECTNESS`: key, nonce, AAD, decrypt compatibility and tests require proof.
- `UNVERIFIED — PRODUCTION CREDENTIAL STATE`: no live credential was accessed or changed.

## Required checks

Trace every caller and raise site; inspect unit tests for malformed keys, nonce uniqueness, encryption/decryption round trips, account isolation, token rotation and revocation. Do not inspect or expose actual production secrets.
