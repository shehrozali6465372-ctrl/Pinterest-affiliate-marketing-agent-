# store_pinterest_credential — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-005`; source `app/credential_vault.py:47-80`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
1. Builds AES-GCM cipher; invalid key fails before DB access.
2. Converts account ID, Pinterest user ID and access token to strings; absent refresh token becomes empty.
3. Encrypts access token using account-bound access AAD and encrypts refresh token only when non-empty.
4. Executes parameterized INSERT ... ON CONFLICT(account_id) DO UPDATE.
5. On conflict, replaces access ciphertext and metadata, sets connected status and timestamp. COALESCE preserves existing refresh ciphertext/expiry when incoming values are NULL.
6. Returns account/user/username/status/timestamp only, never token fields.

## Callers and tests
Called by Hub credential-ingest route and OAuth refresh route. Token-refresh tests mostly mock provider/vault behavior; one opt-in disposable-Postgres persistence case exists. No production DB write occurred.

## Risks
No per-account lock coordinates concurrent refreshes. Direct callers can omit required dict keys and trigger KeyError; route models are the main input validation boundary. Token values must never enter logs or response metadata.
