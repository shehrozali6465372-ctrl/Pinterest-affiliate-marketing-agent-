# Production definition review — configuration, diagnostics, retry and migration entrypoint

Source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0.

## app/config.py — blob SHA 71805b65766c198a428f5418bd2eec5b7f74953f
- Settings: Pydantic BaseSettings; reads .env, ignores extra values; declares APP_API_KEY, DATABASE_URL, Pinterest static token/board and API base URL, Cloudflare token/account/model, DeepSeek API key/base/model, credential-ingest key and token-encryption key.
- clean_secret_values(cls, value): field validator for llm_api_key, cloudflare_api_token and app_api_key; removes Unicode category Cf characters and trims surrounding whitespace. It does not validate credentials or sanitize all secret fields (credential-ingest and encryption key are not included in this validator).
- settings: module-level Settings instance, so environment is read at import/initialization time; changing environment later does not automatically reconstruct the object.

## app/diagnostics.py — blob SHA 8a1f7b8092c99f9102565c721967d0fa2b50609a
- _require_api_key: constant-time app-key gate for all diagnostic routes.
- database_diagnostic: GET endpoint; executes read-only SELECT 1 plus current_database; returns sanitized 503 on failure; reports no DB mutation/Pinterest/provider generation.
- pinterest_read_only_diagnostic: GET endpoint requiring caller account_id; decrypts stored credential and GETs /user_account; classifies missing credential, invalid tag, key config, DB config/query, transport and upstream rejection; does not return token and flags no writes/generation.
- DiagnosticRunInput: validates account ID and product name/details fields with bounded lengths/defaults.
- run_live_diagnostics: POST endpoint; tests DB SELECT 1 and Pinterest account GET; only after both succeed, invokes Workers AI image generation and DeepSeek multimodal content generation. It returns side-effect flags indicating no Pin/board/product persistence, no Cloudflare Images upload and no generated image persistence; provider usage may be billable. This is not a read-only/cost-free diagnostic.

## app/provider_retry.py — blob SHA e654d8e61ac93010ff45fcdda85e5b0856c23850
- retry_delay_seconds(response, retry_number, max_retry_after=8.0): reads Retry-After seconds or HTTP date, treats naive date as UTC, rejects provider delay above configured maximum by returning None, computes capped exponential backoff with small random jitter, and returns the greater bounded delay. Callers decide which status/errors are retryable. It does not itself perform requests/retries.

## scripts/migrate.py — blob SHA 83e9e4551781888892691dc375da7e43fde2c18e
- main(): calls run_migrations(), prints success only after return, and always closes pool in finally. If migration raises, exception propagates after pool close; script has no CLI arguments or environment guard of its own.
- __main__ guard: runs main only when executed as script.

## Security/operational findings
1. Settings validator omits some secret-bearing settings; ensure values are not accidentally logged and configuration validation is explicit.
2. Diagnostics POST invokes real generation APIs; billable usage is possible despite no Pin/DB product mutation.
3. Migration script applies repository SQL to configured DATABASE_URL; operator must verify target environment before running. No migration command was executed.
4. Retry helper returns None for Retry-After beyond max, meaning caller should fail/defer rather than retry earlier than provider requested.
5. No live diagnostics, migration, provider call or DB query was executed during this review.