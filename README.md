# Pinterest Affiliate Marketing Agent — Model 1

Target: USA audience. Niche: Home Decor & Kitchen.

## Locked scope — exactly seven capabilities
1. Publish
2. Pin Idea
3. Description
4. Title
5. Alt Text
6. Affiliate Link
7. Learning Loop

Do not add features outside this scope without explicit approval.

## Engineering status
The repository contains the initial API foundation and product-intake persistence code. Publishing, AI content/image generation, Pinterest analytics ingestion, and predictive ML remain unimplemented until real integrations and evidence are available. No mock publishing, fake analytics, or pretend learning is allowed.

## Local setup
1. Use Python 3.11 or newer.
2. Create and activate a virtual environment: `python -m venv .venv`.
3. Install dependencies: `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set credentials locally.
5. Run the API: `uvicorn app.main:app --reload`.
6. Run tests: `pytest`.

## Current endpoints
- `GET /health`: liveness only; does not prove integrations are ready.
- `GET /readiness`: reports whether required settings are present, not whether credentials work.
- `POST /products/validate`: validates supplied product fields without saving them.
- `POST /products`: creates a product record in PostgreSQL; returns 503 when database access is unavailable.
- `GET /products/{product_id}`: fetches a saved product record.
- `POST /publish`: intentionally returns 501 until real Pinterest publishing is implemented.
- `POST /learning-loop`: intentionally returns 501 until genuine analytics ingestion and evaluation are implemented.

The first database schema is initialized on product-create requests. Before production, replace this bootstrap approach with versioned migrations and a controlled release procedure.

## Configuration
- `DATABASE_URL`: Neon PostgreSQL connection string.
- `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`: authorized Pinterest API access.
- `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`: Cloudflare image-generation integration.
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`: DeepSeek Flash provider settings. Verify exact supported endpoint and model identifier before use.

Never commit secrets. Configure production secrets as server-side environment variables in Render. The user's affiliate URL must be preserved accurately. Do not claim successful publishing, content generation, analytics ingestion, ML training, or deployment without evidence from the real system.
