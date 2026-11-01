# revoke_pinterest_credential — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-008`; source `app/credential_vault.py:128-131`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.

## Behavior
Opens DB connection and executes parameterized UPDATE setting status='revoked' and updated_at=now() for matching account ID. Returns None and does not fetch/check affected-row count. It does not erase encrypted token columns or call Pinterest OAuth revocation.

## Callers and tests
Called by service-key-protected `/integrations/pinterest/operation` disconnect branch. Success means local credential state changed; it does not prove provider-side revocation.

## Risks
Unknown account IDs silently update zero rows while caller still returns disconnected=true. Ciphertext remains stored. Consider checking affected row count and implement provider revocation separately if required. No account was disconnected in this audit.
