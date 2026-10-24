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
Product intake/persistence, versioned content history, and DeepSeek Flash content generation are implemented as code and covered by CI tests. The Pinterest v5 publishing client and API route are also implemented and tested with mocked responses. Real Neon connectivity, live DeepSeek credentials/calls, and real Pinterest publishing have not been verified. Cloudflare image generation, real Pinterest analytics ingestion, and predictive ML remain pending. No mock publishing, fake analytics, or pretend learning is allowed.

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
- `POST /learning-loop`: intentionally returns 501 until real analytics ingestion and evaluation are implemented.

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
- Alt Text is generated using product details and the supplied image URL; verify live provider/image-fetch behaviour before relying on it.
- No real Pinterest API call was made in CI; publish tests use mocked responses.
- Learning Loop remains disabled. Do not train or promote ML without enough suitable real analytics history.
- Passing CI proves tested software contracts, not live database/provider access.
