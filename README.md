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
Product intake/persistence, versioned content history, and a DeepSeek Flash content-generation integration are implemented as code and covered by CI tests. Real Neon connectivity and live DeepSeek credentials/calls still need verification. The Pinterest v5 publish client and request flow are implemented and tested with mocked API responses; real account authorization and a real publish have **not** been verified. Cloudflare image generation, real Pinterest analytics ingestion, and predictive ML remain pending. No mock publishing, fake analytics, or pretend learning is allowed.

## Local setup
1. Use Python 3.11 or newer.
2. Create and activate a virtual environment: `python -m venv .venv`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set real credentials locally.
5. Apply database migrations: `python -m scripts.migrate`.
6. Start API: `uvicorn app.main:app --reload`.
7. Run tests: `python -m pytest -q`.

## Current endpoints
- `GET /health`: liveness only; does not prove integrations are ready.
- `GET /readiness`: reports configuration presence, not whether credentials work.
- `POST /products/validate`: validates product fields without saving them.
- `POST /products`: saves product data to PostgreSQL; returns 503 if persistence is unavailable.
- `GET /products/{product_id}`: retrieves a saved product.
- `POST /products/{product_id}/content`: calls the configured DeepSeek Flash API using product text and the supplied image URL; stores an auditable content version containing Pin Idea, Title, Description, and Alt Text.
- `GET /products/{product_id}/content`: returns version history for the product.
- `POST /publish` with JSON `{"product_id": 123, "content_version_id": 456}`: publishes an existing content version using the official Pinterest v5 API. It uses the actual supplied product image URL and exact affiliate destination link. Success requires a returned Pin ID; duplicate successful attempts are blocked.
- `POST /products/{product_id}/content/{content_version_id}/publish`: version-specific publishing endpoint.
- `POST /learning-loop`: intentionally returns 501 until real analytics ingestion and evaluation are implemented.

If a Pinterest request times out or receives an ambiguous server error, its outcome is recorded as uncertain and automatic retry is blocked. Check the Pinterest board before attempting a retry; this avoids accidental duplicate Pins.

## Versioned database migrations
Migrations are in `migrations/` and tracked in `schema_migrations`. Run them explicitly before using persistence endpoints. DDL does not run per request. Production migration execution must remain a controlled release step and be tested against staging first.

## Configuration
- `DATABASE_URL`: Neon PostgreSQL connection string.
- `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`: authorized Pinterest API access.
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`: server-side Cloudflare Workers AI access; image-generation service is pending.
- `LLM_API_KEY`: DeepSeek API key.
- `LLM_BASE_URL`: defaults to `https://api.deepseek.com`.
- `LLM_MODEL`: defaults to `deepseek-flash`.

Use only server-side environment secrets in Render. Never commit API keys or tokens. The user-supplied affiliate URL is validated and returned without URL normalization, preserving tracking parameters.

## Important limits
- LLM output is content generation, not a prediction of Pin performance.
- Alt Text is currently generated from product details plus an image URL passed to the configured model; live model/image-fetch behavior must be checked against real provider access.
- Only the publishing client contract has been tested so far; no real Pinterest API call was made in CI.
- Learning Loop remains disabled. Do not train or promote ML without sufficient suitable real analytics history.
- CI tests cover contracts using mocks; they do not prove live external-provider access or live database operations.
