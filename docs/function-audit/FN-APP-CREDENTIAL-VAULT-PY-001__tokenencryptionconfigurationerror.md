# TokenEncryptionConfigurationError

- **Unique ID:** `FN-APP-CREDENTIAL-VAULT-PY-001`
- **Source:** `app/credential_vault.py:14-17`
- **Source blob SHA:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Custom configuration exception raised when the encryption key or cipher configuration is invalid. Verify all raise sites, startup failure behavior and whether errors are sanitized before logs/API responses.

## Exact isolated source

```python
class TokenEncryptionConfigurationError(RuntimeError):
    """Raised only when the token-encryption key is missing or invalid."""
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the source blob.
- `VERIFIED — DEFINITION RANGE`: isolated to one definition.
- `UNVERIFIED — CRYPTOGRAPHIC CORRECTNESS`: key, nonce, AAD, decrypt compatibility and tests require proof.
- `UNVERIFIED — PRODUCTION CREDENTIAL STATE`: no live credential was accessed or changed.

## Required checks

Trace every caller and raise site; inspect unit tests for malformed keys, nonce uniqueness, encryption/decryption round trips, account isolation, token rotation and revocation. Do not inspect or expose actual production secrets.
