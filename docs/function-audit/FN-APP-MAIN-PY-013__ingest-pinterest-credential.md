# ingest_pinterest_credential — source-level review

- ID: `FN-APP-MAIN-PY-013`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/credential verification: NOT RUN.

## Behavior
Requires configured credential-ingest service key and constant-time X-Credential-Ingest-Key match; requires encryption key setting; calls store_pinterest_credential with validated payload; returns stored/account/user/status/timestamp only. RuntimeError and other storage failures map to 503; generic errors do not return token fields.

## Security and side effects
This is a real Neon credential write and stores encrypted access/refresh tokens. It is service-key protected separately from APP_API_KEY. No credential payload was submitted and no DB mutation occurred.
