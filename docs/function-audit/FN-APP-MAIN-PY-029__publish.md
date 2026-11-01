# publish — source-level review

- ID: `FN-APP-MAIN-PY-029`; source `app/main.py:681-685`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/publish verification: NOT RUN.

## Behavior
Thin compatibility endpoint accepting PublishRequest and delegating directly to `publish_product_content(product_id, content_version_id)`. Its safety/auth behavior is inherited from the delegated route's function body and the route's own dependency declaration; it does not implement a separate publication state machine or add an idempotency key.

## Tests and risk
`tests/test_api.py` exercises shorthand route alongside the canonical publish route, including missing API-key fail-closed behavior and duplicate success blocking. Since delegation reaches real Pinterest POST /pins, this wrapper is publish-capable and was not invoked. Maintain the same fail-closed auth and ledger semantics; do not add an untracked second path.
