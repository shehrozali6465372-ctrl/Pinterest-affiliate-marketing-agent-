# TokenEncryptionConfigurationError — source-level review

- ID: `FN-APP-CREDENTIAL-VAULT-PY-001`; source `app/credential_vault.py:14-15`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Dedicated RuntimeError subclass with no custom constructor or fields. Raised by _cipher when encryption key is absent, invalid Base64 or not exactly 32 bytes. Callers catch it for readiness/configuration and credential routes. It distinguishes key-configuration failure from DB/provider errors.

## Security
Exception messages describe configuration requirement only and do not include key material. Higher-level routes should continue sanitizing unexpected errors; never log Settings or payload objects.
