# valid_destination — source-level review

- ID: `FN-APP-WORKFLOW-PY-005`; source `app/workflow.py:61-66`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Parses affiliate_url with urlsplit; rejects leading/trailing whitespace, non-http/https scheme, missing netloc and embedded username/password; returns original URL string unchanged to preserve affiliate tracking parameters. It does not perform DNS/IP resolution, follow redirects, validate destination safety, confirm affiliate-program membership or fetch product facts.

## Callers and tests
Pydantic validator on ProductWorkflowInput. Tests verify accepted HTTP(S), malformed scheme, userinfo and URL preservation. Do not interpret syntactic URL validation as affiliate link verification.
