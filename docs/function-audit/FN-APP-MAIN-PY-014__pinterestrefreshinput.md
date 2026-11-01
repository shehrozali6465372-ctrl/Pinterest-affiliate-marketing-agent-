# PinterestRefreshInput — source-level review

- ID: `FN-APP-MAIN-PY-014`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema requires account_id 1–200, client_id 1–500 and client_secret 1–2000. It checks non-empty length only; it does not validate app credentials with Pinterest. Client secret is sensitive request data and must not be logged or returned.

## Callers and side effects
Consumed by refresh_pinterest_credential, which calls Pinterest OAuth endpoint and writes refreshed encrypted credentials to Neon. No OAuth request or token mutation was performed.
