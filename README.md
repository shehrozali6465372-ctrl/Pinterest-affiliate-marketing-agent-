# Pinterest Affiliate Marketing Agent — Model 1

Locked scope (only these seven capabilities):
1. Publish
2. Pin Idea
3. Description
4. Title
5. Alt Text
6. Affiliate Link
7. Learning Loop

Target: USA audience, Home Decor & Kitchen.

## Status
Initial scaffold only. Publishing and analytics require real Pinterest API credentials and permissions. Content generation requires a configured LLM provider. No mock publishing or fake learning is implemented.

## Local setup
1. Python 3.11+
2. `python -m venv .venv`
3. Activate the virtual environment.
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and configure values.
6. Run: `uvicorn app.main:app --reload`
7. Test: `pytest`

## Required environment
- `DATABASE_URL`: Neon PostgreSQL connection string.
- `PINTEREST_ACCESS_TOKEN`: authorized Pinterest API token.
- `PINTEREST_BOARD_ID`: destination board ID.
- `LLM_API_KEY` and `LLM_BASE_URL` / model settings for real content generation.

Never commit secrets. Endpoints must report unavailable integrations honestly; they must not claim success without a real provider response.
