# get_pinterest_refresh_credential — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-007`; source `app/credential_vault.py:102-125`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
1. Builds AES-GCM cipher.
2. Selects refresh ciphertext, account/user metadata, scope, expiry and status by parameterized account ID.
3. Raises LookupError if row is absent, revoked/disconnected, or refresh ciphertext is NULL.
4. Splits first 12 bytes as nonce and decrypts remaining bytes with AAD `{account_id}:refresh`.
5. Returns plaintext refresh token and metadata to trusted server code.

## Callers and tests
Used by `refresh_pinterest_credential`. Token-refresh tests cover missing/revoked credentials and mocked rotation/persistence, plus one opt-in disposable-Postgres case. No live Pinterest OAuth refresh occurred.

## Risks
Expiry validation occurs in the route, not this helper. There is no row lock or serialization of concurrent refreshes. Returned refresh token is highly sensitive process-memory data.
