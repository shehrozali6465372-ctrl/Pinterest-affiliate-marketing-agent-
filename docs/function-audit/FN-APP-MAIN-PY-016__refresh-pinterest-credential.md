# refresh_pinterest_credential — source-level review

- ID: `FN-APP-MAIN-PY-016`; source `app/main.py:251-377`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production OAuth verification: NOT RUN.

## Control flow
1. Requires configured `PINTEREST_CREDENTIAL_INGEST_KEY` and constant-time comparison of `X-Credential-Ingest-Key`; missing config and mismatch return 401.
2. Loads refresh token through `get_pinterest_refresh_credential(account_id)`. Missing token maps 409; invalid AES-GCM tag, invalid encryption config, missing DB config and unexpected lookup errors map to sanitized 503 responses.
3. Validates stored refresh expiry when present. Naive timestamps are treated as UTC; malformed timestamps fail closed; expired token returns 409. NULL expiry remains accepted for legacy credentials.
4. POSTs to configured Pinterest `/oauth/token` with HTTP Basic app credentials, grant_type=refresh_token and continuous_refresh=true. Request/JSON failures map to 502.
5. Requires successful response, dict body and non-empty access_token. 400/401/403 provider responses map to 401; other failures map to 502.
6. Computes access expiry from expires_in. Parses refresh expiry from epoch or refresh_token_expires_in; otherwise preserves stored expiry.
7. Persists new access token and provider-rotated refresh token, falling back to old refresh token if omitted. Persistence failure after provider success returns 503 because local durable state is unconfirmed.
8. Returns expiry metadata only; token values are not returned.

## Callers, tests and risks
Called only as a separate service-key endpoint; publish and Learning Loop paths do not automatically call it. `tests/test_token_refresh.py` covers mocked token exchange, rotation, omission/preservation, expiry errors and secret-free response; one opt-in disposable-Postgres case tests persistence. No live Pinterest OAuth call was made.

No per-account lock or row lock serializes refreshes. Concurrent requests can race with refresh-token rotation; one request may persist stale or invalidated refresh token after another. A network timeout after Pinterest rotates a token but before local persistence is an ambiguous credential state. Implement serialized refresh with durable rotation handling before claiming unattended refresh reliability.
