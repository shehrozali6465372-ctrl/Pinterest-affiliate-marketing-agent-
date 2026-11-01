# Production call graph and risk review — Model 1

Application source baseline: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`. This review is static, based on source fetched at that commit. It does not assert that current deployed services run this exact source.

## 1. Runtime composition and request gates

- `app/main.py` constructs the FastAPI app, includes the diagnostics, learning-loop and end-to-end workflow routers, exposes health/readiness/provider diagnostics, and defines credential, product, publication and compatibility routes.
- API-key protected user operations use `require_api_key` or router-specific constant-time `hmac.compare_digest` checks. OAuth credential ingest/refresh/operation routes instead require `X-Credential-Ingest-Key`; credential ingest additionally requires encryption configuration.
- `app/config.py::Settings` loads environment/.env settings; secret fields have Unicode format-character cleanup. This is normalization, not secret validation or secret management. `settings` is a module-level singleton.
- Lifespan closes the database pool on shutdown. `/health` is process liveness; `/readiness` reports configuration state and is not equivalent to a live DB/Pinterest/LLM write test.

## 2. OAuth and credential lifecycle

1. Modern Living Hub backend submits OAuth credential payload to Agent `POST /integrations/pinterest/credentials` (credential ingest route; protected by the separate service key).
2. `store_pinterest_credential` validates a configured base64 AES-256 key via AESGCM, generates a fresh 12-byte nonce per token, encrypts access and optional refresh tokens with account-specific AAD, and upserts ciphertext and metadata in PostgreSQL. API return excludes token fields.
3. `get_pinterest_credential` and `get_pinterest_refresh_credential` fetch ciphertext, require connected status, decrypt in process memory and return the respective token to trusted server code. AES-GCM authentication binds ciphertext to account and token type.
4. `POST /integrations/pinterest/refresh` requires service key, reads stored refresh token, rejects declared expired or malformed expiry, calls Pinterest OAuth token endpoint using client credentials, handles rotated or omitted refresh token, and re-encrypts/upserts the returned credentials.
5. `POST /integrations/pinterest/operation` exposes a finite operation allowlist: account GET, boards GET, create_board POST, create_pin POST and disconnect. The create operations are real Pinterest write operations; they are not read-only diagnostics. Disconnect revokes local credential status but does not show a provider-side OAuth revocation call in this route.

Important distinction: a refresh endpoint exists and has unit tests, but the inspected workflow and Learning Loop call sites retrieve the access token directly; no shared middleware/dependency automatically refreshes an expired access token before those requests. Automatic refresh on expiry is therefore not established by this code path. A caller/orchestrator must explicitly call the refresh endpoint or the implementation must add a bounded refresh-on-401/expiry mechanism.

## 3. Product and content pipeline

- Product CRUD routes accept user-supplied name/details/affiliate URL. URL validation checks absolute HTTP(S), host and credential-free URL while preserving the original string; it does not perform affiliate product research or extract product facts from a destination URL.
- Content generation loads a stored product, calls `generate_pin_content`, stores provider/model/prompt version and generated fields in content_versions. The DeepSeek client sends product text and image data URL as multimodal input, requests JSON output, parses/validates schema, applies bounded retry/corrective prompt logic, and sanitizes provider metadata/logs.
- Cloudflare Workers AI image generation sends product prompt/details to the configured model, accepts supported image response formats, validates MIME/size, and returns a Base64 data URL. It does not upload to Cloudflare Images or persist an image object in this function despite historical assumptions/naming. Provider generation may be billable.
- Pinterest `image_media_source` converts data URLs to Pinterest image_base64 source and passes through legacy public URLs as image_url. It rejects malformed/small data before API request.

## 4. Two publication paths — distinct semantics

### Versioned product routes

The main product/content endpoints persist product and content versions. The versioned publish route reads product/content, retrieves a configured credential, reserves a publication row, sends Pinterest POST /pins, and persists a confirmed Pin ID. Publication rows enforce a unique content-version/board key; pending/unknown/succeeded states block retry. Failed state may reserve another attempt. A 5xx/transport ambiguity is represented as unknown and requires operator reconciliation.

### End-to-end workflow route

`POST /workflow/publish-product` requires X-API-Key, an Idempotency-Key (8–200 chars), product name/details, affiliate URL and account ID. It:
1. Reads idempotency key and rejects existing product key; DB read failure fails closed.
2. Loads stored account credential and GETs Pinterest user_account before provider generation.
3. Lists boards and creates the configured board if no matching name is found. Board creation is a real Pinterest side effect and may happen before product persistence.
4. Generates image via Cloudflare Workers AI and content via DeepSeek.
5. Atomically persists product + first content version under the idempotency key.
6. Reserves publication attempt, then POSTs /pins with board ID, title, description, alt text, Base64 media source and affiliate URL in Pinterest `link`.
7. Requires a returned Pin ID; success is persisted. Missing ID, 5xx, transport uncertainty or persistence failure after the write is marked/treated as unknown where possible; blind retry is blocked pending verification.

The endpoint is a real publish-capable operation. It was not invoked in this audit. The affiliate URL is a normal Pin destination link, not native Pinterest Product Tag metadata.

## 5. Analytics and Learning Loop

- Learning Loop retrieves a stored access token, selects succeeded publications with non-null Pin IDs for the requested account, requests Pin analytics over a bounded date window, parses supported metrics, and upserts snapshots by Pin/date period.
- It computes aggregate impressions/saves/outbound clicks and descriptive rates. It explicitly returns `model_trained: false`; there is no model fit, persisted weights, feature store, experiment/evaluation framework or learned policy update in this route. It is genuine analytics ingestion but not a machine-learning learning loop.
- The scheduled GitHub Actions workflow POSTs to this endpoint daily. This creates production analytics snapshot writes; it does not prove ML training.

## 6. Diagnostics and observability

- GET database diagnostic runs SELECT 1 and returns database name; GET Pinterest diagnostic decrypts stored credential and GETs /user_account. Both are designed as read-only checks.
- POST /diagnostics/run also runs Workers AI image generation and DeepSeek multimodal content generation after DB/Pinterest prerequisites succeed. It does not create a Pin, board or DB product row, but the generation calls may consume provider credits. It must not be treated as cost-free/read-only in operational runbooks.
- Error responses are mostly sanitized and avoid exposing tokens/provider bodies. Verify any new exception/log path before production use.

## 7. Database and concurrency controls

- Psycopg pool is lazy, uses min_size 1/max_size 5 and checkout health check. A global module-level pool is closed on app shutdown.
- Migration runner creates schema_migrations, obtains transaction-scoped advisory lock, applies numbered SQL in lexical order, and records each migration. Static code does not prove migrations were applied in a live database.
- Content version number allocation uses a per-product advisory transaction lock. Publish reservation uses an advisory lock on version/board plus SELECT FOR UPDATE. Reconciliation uses its own advisory lock and row lock. These are meaningful concurrency controls, but only integration tests against PostgreSQL can validate runtime semantics; fake cursor tests cannot.
- Product + first content version are inserted on one connection/transaction in the end-to-end path. This prevents a failed second insert from leaving the idempotency key/product half-created, assuming normal transaction rollback behavior.

## 8. Prioritized findings

### P1 — Automatic token refresh is not wired into API request paths (source verified)

Refresh is a separate service-key endpoint. Workflow, diagnostics and Learning Loop load access token and make API requests directly. There is no shared expiry-aware refresh dependency in those paths. Expired access token can therefore break analytics/publishing until an external caller explicitly refreshes or reconnects. Add controlled refresh-on-expiry/401 with locking to avoid refresh-token rotation races, or document and enforce an external scheduler/caller. Do not add blind retries for non-idempotent Pin creation.

### P1 — End-to-end workflow creates a Pinterest board before completing product workflow (source verified)

`_ensure_board` may POST /boards before image/content generation and DB persistence. A later provider/DB failure leaves a created board side effect. This does not create a Pin but is not fully side-effect-free on failure. Consider requiring a pre-existing board or explicitly tracking/compensating board creation; never auto-delete a board without owner approval.

### P1 — Publish uncertainty remains operationally sensitive (source verified)

Pinterest write may succeed while response/DB persistence is lost. Unknown-state and operator reconciliation reduce duplicate risk, but operator verification depends on complete board pagination and correct account/board association. Maintain a no-blind-retry runbook and alert on unknown rows.

### P2 — “Learning Loop” is analytics ingestion, not ML (source verified)

No training step exists; model_trained is false. If product requirements mean adaptive content ranking/optimization, that is not implemented. Do not claim ML learning or predictive optimization until there is a defined feature/label dataset, offline evaluation, model artifact/versioning, promotion gate and rollback strategy.

### P2 — No affiliate URL product-research/extraction pipeline in this baseline (source verified)

The endpoint requires product_name and product_details from caller. It does not fetch Amazon product details, validate product availability/price, or derive claims from affiliate URL. This is a capability gap relative to fully autonomous product research; do not treat arbitrary user-provided details as independently verified product facts.

### P2 — Provider diagnostics can incur cost (source verified)

POST /diagnostics/run calls Workers AI and DeepSeek when prerequisites pass. CI workflow checks no Pin/product persistence but cannot make generation free. Keep it manual, gated and budget-monitored.

### P2 — Pinterest operation route exposes direct create_board/create_pin (source verified)

The service-key-protected operation endpoint includes direct Pinterest write operations outside the publication state machine/idempotency/reconciliation flow. If Hub still calls it, this is a parallel path that can bypass publication ledger controls. Restrict or remove create operations if not required; otherwise require idempotency, durable state and audit trail.

### P3 — Legacy publications have null account_id (migration verified)

Migration 007 leaves legacy rows unassigned. Learning Loop filters by account_id, so historical successful Pins with NULL account_id will not be ingested for any account until safely backfilled using authoritative evidence.

## 9. Verification boundary

This document is source-derived static review only. It does not prove current deployment commit, environment variables, provider account permissions, live OAuth lifecycle, current DB schema, actual CI run status or real Pinterest behavior. No tests, provider calls, migration, publication, DB mutation or deployment were performed for this review.