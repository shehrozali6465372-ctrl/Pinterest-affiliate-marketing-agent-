# _encrypt — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-004`; source `app/credential_vault.py:42-44`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
Generates a fresh 12-byte nonce with `os.urandom(12)`, UTF-8 encodes plaintext, calls AES-GCM `encrypt(nonce, plaintext, aad)`, and concatenates nonce + authenticated ciphertext/tag into one byte string. It does not persist data or log plaintext. Callers supply AAD.

## Callers and tests
`store_pinterest_credential` calls it separately for access and non-empty refresh tokens, using account-specific AAD strings `{account_id}:access` and `{account_id}:refresh`. Unit tests exercise local encryption/decryption round-trip and ciphertext separation; no production ciphertext was read.

## Risks
Readers assume first 12 bytes are nonce; changing the layout requires versioning/migration. Nonce uniqueness depends on secure random generation. No secrets were changed.
