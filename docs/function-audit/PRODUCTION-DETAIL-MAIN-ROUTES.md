# Production definition review — app/main.py

Source baseline blob SHA: 37f5ccae0d171a8f8d6766cfb26013dbe221391c.

## Application lifecycle and validation models
- lifespan(app): async context manager; yields control to FastAPI lifespan and closes DB pool in finally during shutdown.
- require_api_key(header): enforces configured APP_API_KEY with hmac.compare_digest; returns 401 for missing config/header/mismatch.
- require_configured_api_key(): factory/dependency builder for fail-closed protected route dependencies.
- ProductInput: Pydantic request model for name/details/affiliate URL. strip_required_text trims and rejects blank strings. validate_affiliate_url_without_rewriting validates absolute HTTP(S), netloc and no URL userinfo while returning the exact original URL.
- PinterestCredentialInput: OAuth credential ingestion schema; fields include account/user identity, access/refresh token, token metadata and expiries. Treat input as secret-bearing; never log/dump.
- PublishRequest: request model for the versioned publish route.
- _serialize_row(row): converts DB row to JSON-compatible representation, including datetime conversion where present.
- health(): process liveness response; does not test database/provider connectivity.
- readiness(): reports configured state for DB, encryption key, Pinterest account flow, provider keys etc.; it is a configuration/readiness signal, not a live provider test.
- provider_diagnostics(): invokes provider access diagnostics (inspect individual checks and distinguish no-billable access probes from generation). Do not infer runtime status from route existence.

## OAuth routes
- ingest_pinterest_credential(payload, X-Credential-Ingest-Key): constant-time service-key gate; requires encryption config; calls credential vault store; returns account metadata only; maps storage/config errors to 503.
- PinterestRefreshInput: requires account ID and Pinterest app client ID/secret; secret-bearing input.
- PinterestOperationInput: accepts account ID, operation name and generic payload dict; the operation route must constrain allowed operations carefully.
- refresh_pinterest_credential(payload, service key): decrypts stored refresh token, validates refresh expiry (null allowed for legacy, malformed/expired fails closed), POSTs OAuth token endpoint, parses rotated tokens/expiry, preserves old refresh token/expiry when provider omits them, encrypts/upserts credentials, and returns expiry metadata only. There is no explicit per-account refresh lock, and ordinary API callers do not automatically call this route.
- pinterest_account_operation(payload, service key): loads credential, then allows account GET, boards GET, create_board POST, create_pin POST, or local disconnect. create_board/create_pin are direct provider writes outside publication ledger; disconnect revokes local credential status but does not demonstrate provider revocation. Validate input fields and returned provider body before trusting.

## Product/content/publication routes
- validate_product(product): validates request and returns normalized/safe product information; no persistence/provider research.
- create_product(product): writes product row and returns saved record; DB configuration/query failures mapped to API errors.
- read_product(product_id): reads one product or returns 404.
- generate_product_content(product_id): loads product, calls DeepSeek content generator, persists a new content version with provider/model/prompt metadata; provider failure and DB failure are separate failure stages.
- list_product_content(product_id): returns saved content versions, newest-first as database helper defines.
- PublicationReconciliationInput: validates operator outcome/evidence and optional Pin ID; evidence_must_be_nonblank strips/rejects blank evidence and applies length bounds.
- get_publication_status(publication_id): DB-only read for operator status; not a Pinterest verification.
- verify_publication_on_pinterest(publication_id): loads publication/account credential, paginates board Pins via read-only helper and reads Pin detail; no Pinterest write; completeness matters before absence can be concluded.
- reconcile_publication(publication_id, payload): authenticated operator path; forwards evidence to DB transition restricted to unknown publication; does not independently create/delete Pins.
- publish_product_content(product_id, content_version_id): versioned publish path; obtains product/content/credential, reserves attempt, generates/uses image source as implemented, posts Pin and persists Pin ID or uncertain/failure state. It is a real write endpoint; do not invoke without explicit separate approval.
- publish(payload): compatibility route; trace route mapping to versioned path and preserve auth/idempotency constraints.
- learning_loop_unavailable(): explicit unavailable fallback handler if route is not mounted; not a training implementation.

## Route-level findings
1. Credential ingest and refresh use separate service key from user-facing APP_API_KEY. Keep secrets separate and rotate independently.
2. PinterestOperationInput route includes direct board/Pin creation, bypassing versioned publication ledger controls.
3. Readiness must not be reported as live provider proof.
4. Read-only verification must prove complete pagination before operator asserts absence.
5. The compatibility route must not become an unguarded second publish path.
6. The source review did not execute any endpoint or mutate production state.