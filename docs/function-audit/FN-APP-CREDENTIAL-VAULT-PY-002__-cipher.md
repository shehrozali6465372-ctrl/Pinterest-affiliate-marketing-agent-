# _cipher — source-level review

- **ID:** `FN-APP-CREDENTIAL-VAULT-PY-002`
- **Source:** `app/credential_vault.py:18-30`
- **Source blob:** `cb700abe4ba4c585966c2545d18211fc2035e2b5`
- **Baseline:** `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Source review:** COMPLETE
- **Runtime verification:** NOT RUN

## Statement-level behavior

1. Reads `settings.pinterest_token_encryption_key`.
2. If the setting is absent or empty, raises `TokenEncryptionConfigurationError` with a configuration-only message.
3. Decodes the value using strict Base64 validation; malformed Base64 is caught and translated to the same dedicated configuration error.
4. Requires the decoded key to be exactly 32 bytes; other lengths fail before cipher construction.
5. Returns a `cryptography` `AESGCM` instance. The raw key is not returned from this helper or logged here.

## Callers and security invariants

`token_encryption_key_is_valid()` uses this helper as a configuration check. Credential storage and retrieval call it to encrypt/decrypt access and refresh tokens. AES-GCM provides authenticated encryption; the caller-supplied associated data binds token ciphertext to account ID and token type. Nonce generation and AAD construction occur in the higher-level helpers, not here.

## Failure paths and limitations

The function validates encoding and key length only. It does not prove that the key can decrypt existing database ciphertext, that the key is securely provisioned, or that rotation has been performed. Replacing the key without re-encrypting stored rows will make existing credentials undecryptable. No plaintext token or key should be logged by callers.

## Tests and evidence

Unit tests cover invalid/missing key configuration and encryption/decryption behavior in mocked/local contexts. Production Neon ciphertext was not read or decrypted.

## Finding

No direct defect in this helper's length/decoding gate was established from static review. Key lifecycle/rotation and live ciphertext compatibility remain operational controls outside this function. No key or credential was changed.
