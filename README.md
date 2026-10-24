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
Product intake/persistence and DeepSeek Flash Pin content generation are implemented as API foundations. Real database connectivity still needs to be configured and verified. Pinterest publishing, Cloudflare image generation, Pinterest analytics ingestion, and predictive ML remain unimplemented. No mock publishing, fake analytics, or pretend learning is allowed.

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
- `GET /readiness`: reports whether required settings are present, not whether credentials work.
- `POST /products/validate`: validates product fields without saving them.
- `POST /products`: saves a product record to PostgreSQL; returns 503 if persistence is unavailable.
- `GET /products/{product_id}`: retrieves a saved product.
- `POST /products/{product_id}/content`: calls the configured DeepSeek Flash API using product text and image URL, then stores an auditable content version (Pin Idea, Title, Description, Alt Text).
- `POST /publish`: intentionally returns 501 until real Pinterest publishing is implemented.
- `POST /learning-loop`: intentionally returns 501 until genuine analytics ingestion and evaluation are implemented.

## Versioned database migrations
Migrations are in `migrations/` and recorded in `schema_migrations`. Run them explicitly before using the persistence endpoints. Do not run DDL per request. Production migration execution should be a controlled release step and should be tested against a staging database first.

## Configuration
- `DATABASE_URL`: Neon PostgreSQL connection string.
- `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`: authorized Pinterest API access.
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`: server-side Cloudflare Workers AI access; image generation route still pending.
- `LLM_API_KEY`: DeepSeek API key.
- `LLM_BASE_URL`: defaults to `https://api.deepseek.com`.
- `LLM_MODEL`: defaults to `deepseek-flash`.

Use only server-side environment secrets in Render. Never commit keys or tokens. The user-supplied affiliate URL is validated and returned without URL normalization, so tracking parameters remain intact.

## Important limits
- A generated response is an LLM output, not a performance prediction.
- Alt text is based on what the selected model can interpret from the supplied image URL; image accessibility/fetch failures must surface as errors, not fabricated visual descriptions.
- Publishing and Learning Loop remain disabled until authorized real integrations and verification tests exist.
- No ML model should be trained or promoted without sufficient suitable real analytics history.
