# clean_secret_values — source-level review

- ID: `FN-APP-CONFIG-PY-002`; source `app/config.py:30-38`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic before-validator receives optional string. None remains None. Otherwise removes every Unicode character whose category is Cf, then trims leading/trailing whitespace. It is attached only to llm_api_key, cloudflare_api_token and app_api_key. It does not validate token authenticity, preserve whitespace intentionally included in secrets, or sanitize Pinterest credential-ingest/encryption key settings.

## Tests and limitations
Config tests exercise invisible formatting characters and normalization. This normalization can alter a secret containing meaningful leading/trailing whitespace (typically not expected for API keys); it does not rotate or redact values. Never print the returned secret.
