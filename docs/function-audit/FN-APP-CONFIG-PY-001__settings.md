# Settings — source-level review

- ID: `FN-APP-CONFIG-PY-001`; source `app/config.py:7-28`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic BaseSettings model loads environment and .env values; extra settings are ignored. Declares APP_API_KEY, DATABASE_URL, legacy Pinterest token/board, Pinterest API base URL, Cloudflare API token/account/model, DeepSeek key/base/model, credential-ingest service key and token-encryption key. Defaults leave most secrets unset; provider URLs/models have defaults. A field validator is attached only to llm_api_key, cloudflare_api_token and app_api_key.

## Callers and risk
A module-level Settings instance is created in config.py and imported by all application modules. The validator does not cover credential-ingest or encryption key fields. Defaults do not prove credentials or account permissions. Environment changes after import do not automatically mutate the singleton. Avoid logging settings objects because they contain secret fields.
