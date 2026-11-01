# readiness — source-level review

- ID: `FN-APP-MAIN-PY-011`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Uses require_api_key dependency (which allows access if APP_API_KEY is unset). Computes configuration-presence booleans for DB, legacy static Pinterest token/board, stored-account workflow prerequisites (DB + valid encryption key), credential-ingest key, Cloudflare token/account, LLM key/model and app API key. Calls token_encryption_key_is_valid, which checks format only. Returns explicit note that presence does not prove credentials, account connection, access or permissions.

## Limits
No DB query, credential decrypt, Pinterest API call or provider generation occurs. It is not live integration proof. When APP_API_KEY is absent, route itself is open because of require_api_key behavior.
