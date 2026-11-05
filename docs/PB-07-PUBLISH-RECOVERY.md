# PB-07 — Safe publication recovery runbook

## Safety rule
Never retry a publication in `pending` or `unknown`. A timed-out POST may have created a Pin. Do not induce an ambiguous publish in production to test recovery.

## Inspect a publication record
Call `GET /publications/{publication_id}` with the configured `X-API-Key`. This is database-only; it does not call Pinterest. Verify publication ID, account ID, board ID, content version ID, status, and last update. Do not include access tokens in evidence or support messages.

## Verify uncertain outcomes (read-only)
1. Using the same connected Pinterest account represented by `account_id`, list Pins on the exact stored board through the official read-only endpoint `GET /v5/boards/{board_id}/pins?page_size=250`.
2. Follow every pagination `bookmark` until it is null. If the response errors, permissions are insufficient, or pagination cannot complete, stop: keep the row `unknown` and do not retry.
3. Match by stored content attributes where available (title, description, link) and creation-time window. Do not rely on title alone. Confirm a candidate Pin ID by a follow-up `GET /v5/pins/{pin_id}` and ensure its `board_id` and destination link agree. If more than one candidate matches, leave `unknown` and escalate for human review.
4. If the Pin exists, use `POST /publications/{publication_id}/reconcile` with `outcome="succeeded"`, the verified `pinterest_pin_id`, and non-secret evidence (which board listing/page and pin detail were checked). The function updates an `unknown` record, or a `pending` record whose `updated_at` is at least 10 minutes old, and stores evidence in `response_metadata.reconciliation`. The 10-minute stale threshold is a safety buffer beyond the gateway's 45-second provider timeout; recent pending records remain non-reconcilable.
5. Only if all pages of the correct board were read successfully and the operator has affirmatively confirmed no matching Pin exists, use `outcome="failed"`, omit the Pin ID, and record the check window and pagination completion in `operator_evidence`. This re-enables retry; therefore never use this outcome based solely on a timeout, one page, search result absence, or a failed API lookup.
6. Re-read `GET /publications/{publication_id}` after reconciliation and verify the stored status and audit evidence. If the record is not `unknown`, do not force a transition.

## API safety properties
- Both inspection and reconciliation require the Agent `X-API-Key`.
- Reconciliation is an explicit operator action; no background worker or automatic retry resolves `unknown`.
- `unknown` records may transition immediately; `pending` records require `updated_at` to be at least 10 minutes old and the same exhaustive operator verification.
- `succeeded` requires a non-empty verified Pin ID; `failed` forbids a Pin ID.
- No endpoint in this runbook publishes, deletes, edits, or creates a Pinterest Pin or board.

## Evidence gate for closing PB-07
Unit tests and the runbook establish a fail-closed mechanism, not a production incident rehearsal. Before marking the blocker fully closed, review the exact-head CI result after the code is reviewed/merged and run a disposable/test-account or provider-stub scenario proving persisted `unknown` -> retry blocked -> read-only board verification -> operator reconciliation -> verified final state. Never perform that scenario by publishing a real production Pin. If no isolated account/provider stub is available, keep PB-07 “implemented, isolated end-to-end verification pending.”

## Provider-generation idempotency reservation (migration 012)

The end-to-end workflow now acquires a PostgreSQL-backed lease keyed by the request's `Idempotency-Key` and a SHA-256 fingerprint of normalized request inputs **before** invoking image or content providers. Concurrent requests with the same key are rejected while a live lease exists; a different payload using the same key is rejected with HTTP 409.

- Lease duration: 10 minutes, longer than the configured maximum provider request/retry path.
- Generated image data URL and model are checkpointed immediately after image generation.
- Generated content and model are checkpointed after content generation.
- A provider-stage failure releases the lease as retryable while preserving completed checkpoints; a content-generation retry can reuse the saved image rather than pay for image generation again.
- Product/content persistence remains atomic. After it succeeds, the reservation is marked `persisted` and large cached provider payloads are cleared before the Pinterest publishing gateway is invoked.
- Every checkpoint/finalization is fenced by the current UUID lease token. A worker whose lease was superseded cannot overwrite the newer worker's checkpoint or complete the reservation.
- A process crash after a provider returns but before its checkpoint commits can still cause that provider call to repeat after lease expiry. Exactly-once execution across independent providers and PostgreSQL is not achievable without provider-supported idempotency.
- Migration 012 is local only and must be applied before deploying this code. Main Neon has not been changed. The historical `009_affiliate_product_scheduler.sql` provenance issue remains a separate migration-release blocker.

The generation reservation is not a Pinterest publishing reservation. All actual Pin writes remain exclusively in `app/publishing_gateway.py`; uncertain Pin outcomes continue to require reconciliation rather than blind retry.


### Lease cleanup hardening — 2026-11-05
Unexpected image/content checkpoint errors, invalid cached content, and late idempotency conflicts now attempt a lease release. Release is best-effort and logged; it never masks the originating error. Regression tests cover these paths. Latest full local Agent suite: **125 passed, 11 skipped**; PostgreSQL-backed cases remain unexecuted locally because no `TEST_DATABASE_URL` is configured.


### Atomic product/content + generation finalization — 2026-11-05
A final review found a crash window between committing the product/content transaction and separately marking its generation reservation persisted. The workflow now finalizes the reservation (including cache clearing and product link) inside the same PostgreSQL transaction that inserts or recovers the product and first content version. A missing/superseded lease token aborts and rolls back the whole transaction. This removes the split-commit recovery window; the old standalone completion helper remains only for compatibility and is no longer used by the workflow. Disposable-PostgreSQL integration tests cover atomic completion and rollback on lost lease.

Latest verification update (2026-11-05): local Agent suite **125 passed, 13 skipped**; the 13 PostgreSQL integration tests (including atomic finalization/rollback) were skipped without `TEST_DATABASE_URL`. A separate isolated Neon branch successfully applied 011+012 and passed SQL-level concurrency, checkpoint lifecycle, expiry recovery, stale-token fencing, and constraint probes. This does not replace running the Python database integration tests against disposable PostgreSQL. Temporary branch cleanup is pending explicit approval; main remains unchanged.
