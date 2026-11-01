# publish_product_end_to_end — Deep audit record

- **Unique ID:** `FN-APP-WORKFLOW-PY-008`
- **Source:** `app/workflow.py:101-255`
- **Source blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`
- **Effect classification:** REAL PUBLISH — calls Pinterest POST /pins; not executed during this audit.

## Purpose

This is the end-to-end endpoint handler which accepts supplied product details, an affiliate destination URL and a Pinterest account ID, then attempts to create a Pin. It does not itself research product facts from the affiliate URL: its required request model is defined separately and requires product_name and product_details.

## Inputs

- `payload`: validated `ProductWorkflowInput` containing product_name, product_details, affiliate_url, account_id, optional board_name/board_description.
- `Idempotency-Key`: mandatory header constrained to 8–200 chars.
- `X-Request-ID`: optional header, max 128 chars.

## Execution flow — in source order

1. **Request correlation:** uses supplied request ID or a UUID, then replaces characters outside a small safe set and caps at 128 chars.
2. **Idempotency preflight:** reads product by idempotency key. If DB state cannot be read, returns HTTP 503 rather than risk a duplicate workflow. If the key already exists, returns HTTP 409 with the existing product ID.
3. **Credential lookup:** fetches encrypted-vault credential for payload.account_id. Missing credential maps to HTTP 404.
4. **OAuth probe:** calls Pinterest `GET /user_account` with the stored access token before calling potentially billable media/LLM providers. Failure is normalized to 401 or 503.
5. **Board resolution:** calls `_ensure_board`; that function reads only the first 100 boards and may create a board if no case-insensitive name match is found. Board creation is a real Pinterest write side effect.
6. **Image generation:** calls Cloudflare-backed `generate_and_host_pin_image`. ImageGenerationError maps to HTTP 503.
7. **Content generation:** calls DeepSeek-backed `generate_pin_content` with supplied facts and generated image URL. ContentGenerationError maps to HTTP 503.
8. **Persistence:** stores product and content version in one helper call, passing `image_url=None` despite having generated media; inspect schema and persistence behavior to understand this design. It stores the affiliate URL as provided.
9. **Publication attempt:** creates an attempt row. If prior state blocks a new attempt, returns the previously succeeded Pin ID or rejects an uncertain/pending attempt with HTTP 409.
10. **Pinterest write request:** constructs payload with board_id, generated title/description/alt_text, media source, and `link: payload.affiliate_url`; sends `POST /pins`.
11. **Outcome classification:** missing Pin ID is marked unknown; provider 5xx or post-publish persistence errors are marked unknown; explicit rejection is marked failed. Secondary DB status-write failures are swallowed in the exception cleanup blocks.
12. **Success response:** returns real persisted Pin ID, product/content IDs and generated content/provider metadata.

## Important code-level observations — not yet fully verified

- This route can publish a real Pin and must never be invoked during read-only analysis.
- It does not auto-research the product from affiliate_url. Both product_name and product_details are required inputs, used for image/content generation.
- Board resolution currently reads `/boards?page_size=100`; no bookmark pagination is present in this helper. A matching board beyond the first page may be missed and a duplicate board may be created. Verify against Pinterest pagination contract and tests.
- Comment says idempotency key is consumed by persistence only after provider generation. That makes failed provider generation retryable, but it also means two concurrent requests could both pass the initial preflight; correctness depends on DB unique constraint/transaction behavior. Must inspect database.py and migration 005 plus concurrency tests.
- Generated media is passed into content generation and Pin publishing; product persistence receives `image_url=None`. Verify whether the DB column is intentionally nullable and whether media provenance is stored elsewhere.
- Return shape differs between already-published and newly-published paths: already-published response omits generated title/description/alt_text, affiliate_url and provider metadata. Confirm API contract expectations.
- A success response depends on both Pinterest returning a Pin ID and DB recording success. If Pinterest succeeds but DB persistence fails, result is deliberately uncertain and must be reconciled before retry.
- Catch blocks swallow exceptions while trying to record failure/unknown state. This avoids masking the original response but can leave a stale publication status; verify recovery and observability.

## Verification tags

- **VERIFIED — SOURCE PRESENT:** exact function body fetched at recorded blob SHA.
- **VERIFIED — CONTROL-FLOW INVENTORY:** major stages above are mapped from source code.
- **UNVERIFIED — CORRECTNESS:** not yet proven by full caller/callee analysis and tests.
- **UNVERIFIED — LIVE PUBLISH:** no Pinterest publish call was made.
- **UNVERIFIED — PRODUCTION DATA:** no production database state was read or changed in this audit.

## Tests and call graph still required

Inspect and map tests for: missing API key; invalid/missing token; account verification failures; board listing >100; board create success/failure; Cloudflare failure; DeepSeek 503/malformed JSON; transaction rollback; concurrent same idempotency key; attempt pending/succeeded/unknown; Pinterest timeout after provider accepted request; missing Pin ID; success persistence failure; affiliate URL preserved; and no duplicate Pin on retry. Trace every callee: `get_product_by_idempotency_key`, `get_pinterest_credential`, `_pinterest_request`, `_ensure_board`, `generate_and_host_pin_image`, `generate_pin_content`, `create_product_with_content_version`, `begin_publish_attempt`, `image_media_source`, `finish_publish_attempt`.
