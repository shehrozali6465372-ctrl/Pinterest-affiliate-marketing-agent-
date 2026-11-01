# token_encryption_key_is_valid

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-003`
- **Source:** `app/credential_vault.py:31-39`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Checks whether configured token-encryption key material can be decoded and is a valid AES key length. Verify accepted encoding, exact byte-length constraints, malformed base64 handling and consistency with _cipher.

## Exact isolated source

```python
def token_encryption_key_is_valid() -> bool:
    """Validate the configured AES-256-GCM key format without reading or exposing secret material."""
    try:
        _cipher()
    except TokenEncryptionConfigurationError:
        return False
    return True
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the source blob.
- `VERIFIED — DEFINITION RANGE`: isolated to one definition.
- `UNVERIFIED — CRYPTOGRAPHIC CORRECTNESS`: key, nonce, AAD, decrypt compatibility and tests require proof.
- `UNVERIFIED — PRODUCTION CREDENTIAL STATE`: no live credential was accessed or changed.

## Required checks

Trace every caller and raise site; inspect unit tests for malformed keys, nonce uniqueness, encryption/decryption round trips, account isolation, token rotation and revocation. Do not inspect or expose actual production secrets.
