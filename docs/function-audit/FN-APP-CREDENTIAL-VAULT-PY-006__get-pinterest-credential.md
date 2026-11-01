# get_pinterest_credential — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-006`; source `app/credential_vault.py:83-99`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
1. Builds AES-GCM cipher before querying DB.
2. Selects credential metadata, access ciphertext and status for exact account ID using a parameterized query.
3. Raises LookupError if row is absent or status is not connected.
4. Converts ciphertext to bytes; first 12 bytes are nonce and remaining bytes are ciphertext/tag.
5. Decrypts with AAD `{account_id}:access`, UTF-8 decodes and returns token plus metadata in process memory.

## Callers and tests
Used by diagnostics, workflow, Learning Loop and Pinterest operation routes. Tests mock vault calls or use local test encryption; live Neon decryption was not performed.

## Risks
InvalidTag propagates when ciphertext, key or AAD fails authentication. Expiry is not checked, so a connected but expired access token can be returned. Returned dict contains plaintext access token and must remain server-side; never serialize/log it.
