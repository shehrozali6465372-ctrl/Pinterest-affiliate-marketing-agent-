# Test-to-production behavior map

Application baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0. This map ties assertions in test modules to production functions. It distinguishes fake/unit coverage from real PostgreSQL integration intent.

| Test module | Production surface exercised | Evidence type and limitation |
|---|---|---|
| test_api.py | main health/readiness/product/content/publish routes; content_generation; pinterest; workflow; diagnostics | FastAPI TestClient with monkeypatched DB/provider clients. Validates route contract and call ordering; no live providers. |
| test_database_pool_recovery.py | database.get_pool, connection, close_pool | Fake ConnectionPool/lease; lifecycle and error propagation only. |
| test_database_pool_recovery_integration.py | psycopg_pool stale connection replacement | Opt-in real PostgreSQL backend termination/recovery. Not executed in this audit; destructive to one DB backend session and guarded to disposable target. |
| test_deepseek_completion.py | content_generation.generate_pin_content and retry helper | Fake DeepSeek HTTP responses; JSON/schema/429/503 behavior, no live API. |
| test_deepseek_failure_diagnostics.py | diagnostics.run_live_diagnostics, content generation error sanitization | Fake DB/Pinterest/Cloudflare and injected exception; no provider usage. |
| test_deepseek_http_diagnostics.py | content_generation HTTP metadata sanitizer/retry | Synthetic httpx responses; validates correlation fields/redaction, not actual provider headers. |
| test_diagnostics.py | diagnostics auth, DB diagnostic, Pinterest read-only diagnostic, app lifespan | TestClient and fake vault/HTTP/DB; route mapping and redaction only. |
| test_image_base64.py | pinterest.image_media_source | Pure helper tests for data URL vs legacy URL and invalid input. |
| test_learning.py | learning._number and run_learning_loop | Fake DB and Pinterest analytics responses; metric parsing/persistence call assertions, not Neon durability. |
| test_pinterest_readonly.py | pinterest.list_board_pins_read_only and get_pin_read_only | Fake HTTP pages; pagination/repeated bookmark/page cap/error handling, not live Pinterest. |
| test_postgres_publication_recovery.py | database publication reservation/reconciliation/migrations and API reconciliation | Designed for disposable PostgreSQL; validates durable state, migration idempotency and HTTP round-trip when run. Execution not proven by this audit. |
| test_provider_retry.py | provider_retry.retry_delay_seconds and media_generation Cloudflare retry | Fake responses; bounded Retry-After and selected retry policy. |
| test_publish_reconciliation.py | main publication status/verification/reconciliation routes; database.reconcile_unknown_publication | Mix of TestClient and stateful in-memory SQL harness; does not model actual row locks. |
| test_publish_recovery_state_machine.py | database.begin_publish_attempt | Fake cursor/state; state transitions only, not transaction concurrency. |
| test_token_refresh.py | main.refresh_pinterest_credential and credential_vault.store/get refresh credential | Mostly mocked OAuth response and vault store; one opt-in disposable-Postgres persistence case. No live Pinterest OAuth call. |
| test_workflow_persistence_recovery.py | workflow.publish_product_end_to_end and database persistence helpers | Fake generation/DB/Pinterest callbacks; validates failure ordering and unknown-state classification, not real write. |
| test_workflow_recovery.py | workflow._pinterest_request and workflow endpoint error mapping | Fake HTTP timeout/5xx; no network call. |

## Coverage gaps and interpretation

1. No test proves live Pinterest OAuth refresh token rotation against the user's connected account.
2. No test in this suite proves automatic access-token refresh is wired into normal publish/analytics requests; current route source indicates it is not.
3. No test proves the end-to-end board resolver paginates beyond its first 100 board records.
4. Fake publication-state harnesses cannot prove PostgreSQL row-lock/advisory-lock concurrency; the opt-in disposable DB tests are needed.
5. Test names asserting “real” or “not faked” describe implementation expectations; they are not proof of a live production Pin. The audit itself did not publish.
6. No test proves predictive ML training; Learning Loop tests prove analytics parsing/persistence behavior and model_trained=false.
7. Provider diagnostic tests stub generation. The manual safe-production-diagnostics workflow is the only reviewed route that calls real provider generation; it may be billable and was not dispatched.

No test suite was run during this audit. This map is based on test source and assertions, not a fresh CI result.