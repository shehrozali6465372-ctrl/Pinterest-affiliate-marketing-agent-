# Pinterest Affiliate Marketing Agent — Model 1

Target audience: USA. Niche: Home Decor & Kitchen.

## Locked scope — exactly seven capabilities
1. Publish
2. Pin Idea
3. Description
4. Title
5. Alt Text
6. Affiliate Link
7. Learning Loop

Do not add product capabilities outside this scope without explicit approval.

## Engineering status
Product intake/persistence, versioned content history, DeepSeek Flash content generation, Cloudflare image generation, Pinterest v5 publishing, encrypted OAuth credential storage/refresh, and account-scoped Pinterest analytics ingestion are implemented as code and covered by CI tests. A real Pinterest account authorization and one successful real Pin publish have been verified in the project history; broader repeatability, OAuth refresh lifecycle, production migration execution, and a persisted production analytics snapshot must be tracked as separate verification gates. Predictive ML remains intentionally deferred until sufficient real longitudinal data exists. No mock publishing, fake analytics, or pretend learning is allowed.

## Local setup
1. Use Python 3.11 or newer.
2. Create and activate a virtual environment: `python -m venv .venv`.
3. Install developer/test dependencies: `pip install -r requirements.txt -r requirements-dev.txt`. Production deployments install only `requirements.txt`.
4. Copy `.env.example` to `.env` and set real credentials locally.
5. Apply database migrations: `python -m scripts.migrate`.
6. Start API: `uvicorn app.main:app --reload`.
7. Run tests: `python -m pytest -q`.

## API security
Set a strong random `APP_API_KEY` in Render environment variables before exposing the API. Operational endpoints require it in the `X-API-Key` request header. If `APP_API_KEY` is unset, protected endpoints fail closed with HTTP 503. The `/health` liveness endpoint remains public. Use HTTPS and never put the key in a public client or repository.

## Current endpoints
- `GET /health`: public liveness only; does not prove integrations are ready.
- `GET /readiness`: protected configuration/readiness summary; never returns credential values.
- `POST /products/validate`, `POST /products`, `GET /products/{product_id}`, and content-version routes: product/content management.
- `POST /workflow/publish-product`: Model 1 generation workflow; requires `X-API-Key`, `Idempotency-Key`, and a connected `account_id` in the JSON body. It resolves an existing Pinterest board through read-only paginated GET requests and does not create a board.
- `POST /integrations/pinterest/publish-manual`: Modern Living Hub manual publishing handoff; requires `X-Credential-Ingest-Key` and `Idempotency-Key`. It verifies the stored account identity and selected board before delegating to the canonical publisher.
- `GET /publications/{publication_id}` and `GET /publications/{publication_id}/pinterest-verification`: protected publication status and read-only board/Pin verification. The verification route never creates or changes Pinterest objects.
- `POST /publications/{publication_id}/reconcile`: operator-authenticated state reconciliation only; it never sends a Pin write.
- `POST /integrations/pinterest/analytics/run` and `POST /learning-loop/run`: organic Pinterest analytics ingestion and descriptive reporting. Missing provider metrics remain `null`; they are not fabricated as zero.
- `POST /integrations/pinterest/operation`: bounded account/board/disconnect operations; unsupported operations such as generic `create_pin` are rejected.
- Legacy `POST /publish` and `POST /products/{product_id}/content/{content_version_id}/publish` return HTTP 410 and cannot publish.

Every Pin creation path delegates to `app/publishing_gateway.py`; it contains the sole application HTTP `POST /pins` call. The gateway validates Pin text and required fields before reserving the ledger, blocks pending/unknown/succeeded duplicates, and records definite or uncertain outcomes. Unknown outcomes require read-only verification and explicit operator reconciliation before any retry. The generic workflow Pinterest helper also rejects direct `POST /pins` calls.

The workflow generation reservation stores an idempotency fingerprint, lease, and reusable image/content checkpoints. Reusing a key with a different request is rejected; a live lease blocks concurrent provider calls; retryable failures can reuse completed checkpoints. A process crash between a provider response and its checkpoint commit can still cause that provider stage to run again after lease expiry; exactly-once provider billing cannot be guaranteed.

Pinterest credentials are selected by account ID from the encrypted Neon credential vault. OAuth refresh is a separate protected operation; do not force expiry or rotate a valid production credential for testing. `ads:read`, advertiser-account discovery, and audience insights are deferred to Model 2 and are not active in the current Hub/Agent integration.

## Versioned database migrations
Migrations are in `migrations/` and tracked in `schema_migrations`. Run them explicitly before using persistence endpoints. DDL does not run per request. Production migration execution should be a controlled release step and tested against staging first.

## Configuration
- `APP_API_KEY`: protect operational endpoints.
- `DATABASE_URL`: Neon PostgreSQL connection string.
- - `PINTEREST_ACCESS_TOKEN`: deprecated legacy value; active publishing routes use the encrypted OAuth credential vault and do not read this token.
- `PINTEREST_TOKEN_ENCRYPTION_KEY`: decrypts the OAuth credential stored in Neon; it must remain identical to the key used to encrypt existing credentials.
- `PINTEREST_CLIENT_ID` and `PINTEREST_CLIENT_SECRET`: Pinterest developer app credentials, stored only in the Agent server environment and used by the protected OAuth refresh flow. Never force expiry or rotate a valid production credential for testing.
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`: server-side Cloudflare Workers AI image-generation access. `CLOUDFLARE_IMAGE_MAX_BYTES` defaults to 10 MiB and bounds the streamed image response.
- `LLM_API_KEY`: DeepSeek API key.
- `LLM_BASE_URL`: defaults to `https://api.deepseek.com`.
- `LLM_MODEL`: defaults to `deepseek-flash`.

Use only server-side environment secrets in Render. Never commit API keys or tokens. The user-supplied affiliate URL is validated and returned without URL normalization, preserving tracking parameters.

## Important limits
- LLM output is content generation, not a prediction of Pin performance.
- DeepSeek receives text-only input; generated Alt Text is a cautious draft based on supplied product facts and intended composition, not visual inspection. Verify it against the final image before publication.
- No real Pinterest API call was made in CI; publish tests use mocked responses.
- Learning Loop records real Pinterest analytics and descriptive summaries; it does not train a predictive ML model. Do not claim predictive learning until enough suitable real analytics history and a validated model/evaluation pipeline exist.
- Passing CI proves tested software contracts, not live database/provider access.

## End-to-end workflow (new, requires live verification)

The authenticated endpoint is included in `main`:

`POST /workflow/publish-product`

It verifies the connected account and resolves an existing requested board through read-only paginated GET requests, generates a product lifestyle image with Cloudflare Workers AI, generates Pin Idea/title/description/alt text with DeepSeek, checkpoints reusable outputs, persists the product and content version, publishes through the canonical Pinterest publication gateway, and records the returned Pin ID. It does not create a missing board.

Required server-side Render environment:
- `APP_API_KEY`: required by the new workflow endpoint.
- `DATABASE_URL`: Neon database URL containing the existing credential vault and publication tables.
- `PINTEREST_TOKEN_ENCRYPTION_KEY`: same base64-encoded 32-byte key used to encrypt the already-stored Pinterest credential.
- `CLOUDFLARE_API_TOKEN`: token with Workers AI Run permission. The current `image_base64` flow does not upload to Cloudflare Images.
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account that owns Workers AI.
- `LLM_API_KEY`: DeepSeek API key.
- Optional: `CLOUDFLARE_IMAGE_MODEL` (default `@cf/black-forest-labs/flux-1-schnell`), `LLM_MODEL`, `LLM_BASE_URL`, `PINTEREST_API_BASE_URL`.

Example request (send `X-API-Key` securely; include a unique `Idempotency-Key` for each new publish request and reuse that same key when retrying; do not place secrets in source code):
```json
{
  "product_name": "Copco 3-Tier Spice Rack Organizer",
  "product_details": "Three-tier spice rack organizer for keeping spice containers visible and accessible. Verify dimensions and materials against the product listing before including those details.",
  "affiliate_url": "https://link.amazon/B01vlJZST",
  "account_id": "pinterest:1069323642682526567",
  "board_name": "Kitchen Organization Ideas",
  "board_description": "Practical kitchen organization and pantry storage ideas."
}
```

Idempotency: `Idempotency-Key` is required (8–200 characters). The request fingerprint is bound to the key. A different payload with the same key returns HTTP 409; a concurrent active generation returns HTTP 409 with a retry hint. A retry with the same key can recover persisted image/content checkpoints. Publication pending/unknown/succeeded states still block blind duplicate Pin creation; inspect and reconcile before retrying an uncertain publish.

Important: keep the `DATABASE_URL` pointed at the intended Neon database and keep `PINTEREST_TOKEN_ENCRYPTION_KEY` identical to the key used for existing credentials. Pinterest receives generated image bytes using its documented `image_base64` media source; no Cloudflare Images upload or public image URL is required. New workflow product rows store `image_url = NULL` to avoid persisting Base64 image payloads. Provider diagnostics have verified the live database and Pinterest account read, DeepSeek model access, and Cloudflare Workers AI API access; a prior real diagnostic also exercised image/content generation. The complete `/workflow/publish-product` route must still only be considered live-verified after a user-approved new publication returns a real Pin ID and the publication record is checked. Never call it as a diagnostic: it publishes a real Pin and provider usage may be billable. Check the board and publication record before retrying any request with an uncertain outcome.


### Generated image storage
Generated image bytes are kept in process memory only and sent to Pinterest through `media_source.source_type=image_base64`. The workflow stores product/content/publication metadata in Neon, not the Base64 image payload. The legacy `products.image_url` column remains nullable for compatibility with older product records; new workflow-created products leave it NULL. This avoids Base64 bloat in PostgreSQL and API responses and removes the Cloudflare Images hosting dependency. Pinterest's `image_base64` source is documented in the official [Create Boards and Pins API](https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/).


## Current verification note — 2026-10-27

The earlier statement that real Pinterest publishing was wholly unverified is superseded: the project history records one approved real Pin published and verified at https://www.pinterest.com/pin/1069323505300280780/. Do not publish another Pin without separate explicit approval. PB-03 is closed by merged PR #21; do not reopen it. Real OAuth consent/handoff, real token-refresh lifecycle, and a persisted production analytics snapshot are separate gates and must not be conflated with the successful Pin.

## Organic Analytics and Model 2 boundary

The current Learning Loop ingests organic Pin metrics for impressions, saves, Pin clicks, and outbound clicks. Missing values remain unknown (`null`); derived rates are calculated only when the required source metrics are present. It stores descriptive snapshots and does not train a predictive ML model.

Advertiser-account discovery, audience insights, and the Pinterest `ads:read` OAuth scope are **deferred to Model 2**. They are not exposed in the current Modern Living Hub UI or active Agent routes. Do not request `ads:read`, reconnect the account, or trigger new consent for Model 1. Historical audience-insight migration artifacts, if present, do not mean the feature is enabled.
