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
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set real credentials locally.
5. Apply database migrations: `python -m scripts.migrate`.
6. Start API: `uvicorn app.main:app --reload`.
7. Run tests: `python -m pytest -q`.

## API security
Set a strong random `APP_API_KEY` in Render environment variables before exposing the API. Operational endpoints require it in the `X-API-Key` request header when configured. The `/health` liveness endpoint remains public. If `APP_API_KEY` is unset, the API is not protected by this application-level key, so do not expose it publicly until configured. Use HTTPS and never put the key in a public client or repository.

## Current endpoints
- `GET /health`: public liveness only; does not prove integrations are ready.
- `GET /readiness`: reports configuration presence, not whether credentials work.
- `POST /products/validate`: validates product fields without saving them.
- `POST /products`: saves product data to PostgreSQL; returns 503 if persistence is unavailable.
- `GET /products/{product_id}`: retrieves a saved product.
- `POST /products/{product_id}/content`: calls the configured DeepSeek Flash API using product text and supplied image URL; stores an auditable content version containing Pin Idea, Title, Description, and Alt Text.
- `GET /products/{product_id}/content`: returns version history for the product.
- `POST /publish` with JSON `{"product_id": 123, "content_version_id": 456}`: publishes an existing content version using the Pinterest v5 API. The original product image URL and exact affiliate destination link are used. Success requires a returned Pin ID, and successful duplicate attempts are blocked.
- `POST /products/{product_id}/content/{content_version_id}/publish`: version-specific publishing endpoint.
- `POST /learning-loop/run`: protected, real account-scoped Pinterest analytics ingestion; persists snapshots and descriptive aggregates. It does not train predictive ML.\n- `POST /learning-loop` (legacy): returns 501; use `/learning-loop/run` for the real Learning Loop.

A timed-out Pinterest request or ambiguous server error is recorded as uncertain; automatic retry is blocked. Check the Pinterest board before attempting a retry to avoid accidental duplicate Pins.

## Versioned database migrations
Migrations are in `migrations/` and tracked in `schema_migrations`. Run them explicitly before using persistence endpoints. DDL does not run per request. Production migration execution should be a controlled release step and tested against staging first.

## Configuration
- `APP_API_KEY`: protect operational endpoints.
- `DATABASE_URL`: Neon PostgreSQL connection string.
- `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`: authorized Pinterest API access.
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`: server-side Cloudflare Workers AI access; image-generation service is pending.
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

It generates a product lifestyle image with Cloudflare Workers AI, converts the generated image to a data URL and sends it directly to Pinterest using image_base64 (no separate image-hosting service), then generates Pin Idea/title/description/alt text with DeepSeek, stores the product and content version, finds or creates the requested Pinterest board using the encrypted OAuth credential in Neon, publishes through Pinterest API v5, and records the returned Pin ID.

Required server-side Render environment:
- `APP_API_KEY`: required by the new workflow endpoint.
- `DATABASE_URL`: Neon database URL containing the existing credential vault and publication tables.
- `PINTEREST_TOKEN_ENCRYPTION_KEY`: same base64-encoded 32-byte key used to encrypt the already-stored Pinterest credential.
- `CLOUDFLARE_API_TOKEN`: token with Workers AI Run permission. The current `image_base64` flow does not upload to Cloudflare Images.
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account that owns Workers AI and Images.
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

Idempotency: `Idempotency-Key` is required (8–200 characters). A key already accepted for a product is rejected with HTTP 409 to prevent accidentally starting a duplicate workflow. Reuse the original key on retry. Because this endpoint fails closed with HTTP 409 rather than replaying a stored response, reconcile the existing product/publication record before taking any further action; never use a new key merely to bypass a 409.

Important: keep the `DATABASE_URL` pointed at the intended Neon database and keep `PINTEREST_TOKEN_ENCRYPTION_KEY` identical to the key used for existing credentials. Pinterest receives generated image bytes using its documented `image_base64` media source; no Cloudflare Images upload or public image URL is required. New workflow product rows store `image_url = NULL` to avoid persisting Base64 image payloads. Provider diagnostics have verified the live database and Pinterest account read, DeepSeek model access, and Cloudflare Workers AI API access; a prior real diagnostic also exercised image/content generation. The complete `/workflow/publish-product` route must still only be considered live-verified after a user-approved new publication returns a real Pin ID and the publication record is checked. Never call it as a diagnostic: it publishes a real Pin and provider usage may be billable. Check the board and publication record before retrying any request with an uncertain outcome.


### Generated image storage
Generated image bytes are kept in process memory only and sent to Pinterest through `media_source.source_type=image_base64`. The workflow stores product/content/publication metadata in Neon, not the Base64 image payload. The legacy `products.image_url` column remains nullable for compatibility with older product records; new workflow-created products leave it NULL. This avoids Base64 bloat in PostgreSQL and API responses and removes the Cloudflare Images hosting dependency. Pinterest's `image_base64` source is documented in the official [Create Boards and Pins API](https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/).


## Current verification note — 2026-10-27

The earlier statement that real Pinterest publishing was wholly unverified is superseded: the project history records one approved real Pin published and verified at https://www.pinterest.com/pin/1069323505300280780/. Do not publish another Pin without separate explicit approval. PB-03 is closed by merged PR #21; do not reopen it. Real OAuth consent/handoff, real token-refresh lifecycle, and a persisted production analytics snapshot are separate gates and must not be conflated with the successful Pin.
