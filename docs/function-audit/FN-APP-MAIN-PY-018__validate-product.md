# validate_product — source-level review

- ID: `FN-APP-MAIN-PY-018`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Receives ProductInput after dependency auth; returns valid=true plus product name, image URL, original affiliate URL and explicit validation-only next_step. No DB/provider/Pinterest calls or persistence. Since it uses require_api_key, it is accessible when APP_API_KEY is unset. ProductInput enforces syntactic validation, not product fact verification.

## Tests
API tests check preserved affiliate URL and malformed URL/blank-name rejection; no live provider is involved.
