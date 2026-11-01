# token_encryption_key_is_valid — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-003`; source `app/credential_vault.py:31-39`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
Calls `_cipher()`. If that helper raises `TokenEncryptionConfigurationError` for absent, malformed Base64 or non-32-byte key, returns `False`; otherwise returns `True`. It does not catch unrelated exceptions, inspect existing ciphertext, or test decryptability of stored tokens. The result is a configuration-format check, not proof that production credentials can be decrypted.

## Callers and tests
Used by `/readiness` to report encryption-key format validity. Credential storage and retrieval call `_cipher` directly and still raise on invalid configuration. API tests cover absent/invalid key readiness behavior; this is not a live Neon decrypt test.

## Risk
Key rotation without re-encrypting existing rows makes old ciphertext unreadable even if the new key passes this format check. No key or ciphertext was accessed in this audit.
