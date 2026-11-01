# Production definition review — app/credential_vault.py

Source baseline blob SHA: cb700abe4ba4c585966c2545d18211fc2035e2b5.

- TokenEncryptionConfigurationError: explicit configuration failure type for missing/invalid encryption key.
- _cipher(): reads configured key, strict Base64-decodes it, requires exactly 32 bytes, constructs AESGCM. Key material is not returned or logged.
- token_encryption_key_is_valid(): boolean wrapper around _cipher(); validates format only, not whether existing ciphertext can be decrypted.
- _encrypt(cipher, value, aad): generates 12-byte random nonce, UTF-8 encodes value, encrypts with AES-GCM and supplied associated data; stores nonce concatenated with ciphertext/tag.
- store_pinterest_credential(payload): extracts account/user/access/refresh fields, encrypts access token with account-specific access AAD and optional refresh token with refresh AAD, then UPSERTs ciphertext and metadata. On conflict, missing new refresh token and refresh expiry preserve old stored values. Returns only non-secret account metadata.
- get_pinterest_credential(account_id): decrypts key, reads connected credential row, rejects absent/revoked rows, decrypts access ciphertext using nonce prefix and account-specific AAD, returns token in process memory with metadata.
- get_pinterest_refresh_credential(account_id): analogous retrieval for refresh ciphertext; rejects absent/revoked/missing refresh token; returns refresh token only to trusted server code.
- revoke_pinterest_credential(account_id): marks local row revoked and updates timestamp; does not call Pinterest OAuth revocation endpoint.

Security and reliability notes:
1. AES-GCM authenticates ciphertext and AAD; account ID/token type binding prevents moving ciphertext between account/token columns undetected.
2. Key rotation is not implemented in this module. Rotating encryption key without re-encrypting stored ciphertext will make existing tokens undecryptable.
3. Store upsert preserves existing refresh token only when incoming refresh ciphertext is NULL; callers should avoid passing empty-but-present token strings unless they intend to replace.
4. No per-account row lock coordinates concurrent token refreshes. Rotating refresh tokens can race if multiple callers refresh simultaneously.
5. Revocation is local status change, not proof provider-side token was revoked.
6. Database operations were not executed in this audit.