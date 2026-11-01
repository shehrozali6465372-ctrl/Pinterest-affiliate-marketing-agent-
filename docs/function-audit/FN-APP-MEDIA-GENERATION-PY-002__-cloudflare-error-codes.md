# _cloudflare_error_codes — source-level review

- ID: `FN-APP-MEDIA-GENERATION-PY-002`; source `app/media_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Attempts response.json(); obtains `errors` only when body is a dict; iterates at most first three entries; appends `code` only when each entry is a dict and code is int/string. Invalid JSON returns empty list. Does not expose provider message/body. It is a parser, not a retry decision.

## Callers and tests
Used by _safe_cloudflare_error and generation retry policy (including provider code 3040). Synthetic response tests cover parsing and retry decisions. Real Cloudflare error payload shape was not checked live.
