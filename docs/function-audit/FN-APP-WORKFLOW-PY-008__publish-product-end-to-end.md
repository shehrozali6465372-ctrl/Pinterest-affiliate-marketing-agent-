# publish_product_end_to_end — source-level review

- ID: `FN-APP-WORKFLOW-PY-008`; source `app/workflow.py:101-255`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/production verification: NOT RUN.
- Effect classification: REAL Pinterest publish-capable endpoint; not invoked.

## Execution order
1. Creates sanitized request correlation ID.
2. Reads existing product by Idempotency-Key; DB read failure fails closed; existing key returns conflict.
3. Loads stored credential for requested account; missing credential returns 404.
4. GETs Pinterest /user_account before billable generation.
5. Calls _ensure_board; it inspects only first 100 boards and may POST /boards before the remaining workflow succeeds.
6. Calls Cloudflare Workers AI image generation, then DeepSeek content generation. These are external provider calls and may be billable.
7. Atomically persists product and first content version through one DB helper; generated image bytes are sent to Pinterest using `image_base64`; `products.image_url` is explicitly NULL so Base64 bytes are not persisted in Neon.
8. Reserves publication attempt through database state machine.
9. POSTs /pins with title, description, alt text, media source and affiliate URL in Pinterest `link`.
10. Requires returned Pin ID and records success. Missing ID, 5xx/transport uncertainty or persistence failure after provider write must remain unknown and require operator reconciliation.

## Failure, idempotency and test mapping
The product idempotency key is first checked before external calls but persisted only after generation; the database unique index is therefore essential under concurrent requests. A board may be created before provider/persistence failure, leaving an orphan board. A Pinterest write can succeed while response or DB persistence is lost; never blindly retry unknown outcomes.

`tests/test_workflow_persistence_recovery.py` and `tests/test_workflow_recovery.py` use fake providers/DB to exercise ordering and error classification; they do not prove live Pinterest behavior or DB lock semantics. No real Pin was published in this audit.
