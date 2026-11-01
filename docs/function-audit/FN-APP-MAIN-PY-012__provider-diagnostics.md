# provider_diagnostics — source-level review

- ID: `FN-APP-MAIN-PY-012`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime provider verification: NOT RUN.

## Behavior
Uses require_api_key dependency; reports configured/verified fields for DeepSeek and Cloudflare. When keys exist, sends GET to DeepSeek /models and Cloudflare Workers AI models/search endpoint using bounded 12s/5s timeout. Reports HTTP status and check label; HTTP errors become sanitized unreachable result. No image/LLM generation or DB mutation is performed.

## Risk and evidence
Provider access probe is non-generative, but it is still a live external request if invoked. Route is fail-open when APP_API_KEY is unset. Tests mock clients; no provider request was made.
