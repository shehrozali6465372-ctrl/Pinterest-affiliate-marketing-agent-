# validate_affiliate_url_without_rewriting — source-level review

- ID: `FN-APP-MAIN-PY-006`; source `app/main.py:79-88`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Rejects leading/trailing whitespace; parses with urlsplit; permits only http/https scheme (case-insensitive), requires netloc and rejects embedded username/password; returns original string unchanged to preserve tracking parameters/encoding. Does not resolve DNS, inspect redirects or prove affiliate program ownership.

## Callers and tests
Used by ProductInput. API tests assert exact affiliate URL string preservation and reject javascript scheme. This is syntactic validation only.
