# _encrypt

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-004`
- **Source:** `app/credential_vault.py:40-44`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Encrypts a token using the configured authenticated cipher, nonce and associated data. Verify nonce generation uniqueness, ciphertext format, AAD binding, exception propagation and compatibility with decryption.

## Exact isolated source

```python
def _encrypt(cipher: AESGCM, value: str, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + cipher.encrypt(nonce, value.encode("utf-8"), aad)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the source blob.
- `VERIFIED — DEFINITION RANGE`: isolated to one definition.
- `UNVERIFIED — CRYPTOGRAPHIC CORRECTNESS`: key, nonce, AAD, decrypt compatibility and tests require proof.
- `UNVERIFIED — PRODUCTION CREDENTIAL STATE`: no live credential was accessed or changed.

## Required checks

Trace every caller and raise site; inspect unit tests for malformed keys, nonce uniqueness, encryption/decryption round trips, account isolation, token rotation and revocation. Do not inspect or expose actual production secrets.
