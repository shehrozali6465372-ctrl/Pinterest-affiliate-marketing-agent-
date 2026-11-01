# health — source-level review

- ID: `FN-APP-MAIN-PY-010`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Returns static JSON `status=ok` and service identifier. It performs no DB, provider, credential or Pinterest request and proves only that the FastAPI process can answer this route. It is a liveness signal, not readiness or end-to-end health.

## Caller and operational note
Used by uptime/platform health checks. Do not infer Neon, OAuth, DeepSeek or Cloudflare connectivity from HTTP 200 on /health.
