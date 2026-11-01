# PinterestCredentialInput — source-level review

- ID: `FN-APP-MAIN-PY-007`; source `app/main.py:91-101`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema requires account_id, pinterest_user_id and access_token with bounded lengths; username, refresh_token, token_type and scope have defaults/limits; access/refresh expiry strings are optional. It validates shape/length only, not OAuth authenticity, expiry format, scope validity or account ownership.

## Callers and security
Used by Hub-to-Agent credential-ingest endpoint. Payload contains bearer and refresh secrets; route sends model_dump to credential vault, which encrypts before Neon persistence. Never log or return the model payload.
