# PB-07 — Safe publication recovery runbook

## Safety rule
Never retry a publication in `pending` or `unknown`. A timed-out POST may have created a Pin. Do not induce an ambiguous publish in production to test recovery.

## Inspect a publication record
Call `GET /publications/{publication_id}` with the configured `X-API-Key`. This is database-only; it does not call Pinterest. Verify publication ID, account ID, board ID, content version ID, status, and last update. Do not include access tokens in evidence or support messages.

## Verify uncertain outcomes (read-only)
1. Using the same connected Pinterest account represented by `account_id`, list Pins on the exact stored board through the official read-only endpoint `GET /v5/boards/{board_id}/pins?page_size=250`.
2. Follow every pagination `bookmark` until it is null. If the response errors, permissions are insufficient, or pagination cannot complete, stop: keep the row `unknown` and do not retry.
3. Match by stored content attributes where available (title, description, link) and creation-time window. Do not rely on title alone. Confirm a candidate Pin ID by a follow-up `GET /v5/pins/{pin_id}` and ensure its `board_id` and destination link agree. If more than one candidate matches, leave `unknown` and escalate for human review.
4. If the Pin exists, use `POST /publications/{publication_id}/reconcile` with `outcome="succeeded"`, the verified `pinterest_pin_id`, and non-secret evidence (which board listing/page and pin detail were checked). The function only updates an existing `unknown` record and stores evidence in `response_metadata.reconciliation`.
5. Only if all pages of the correct board were read successfully and the operator has affirmatively confirmed no matching Pin exists, use `outcome="failed"`, omit the Pin ID, and record the check window and pagination completion in `operator_evidence`. This re-enables retry; therefore never use this outcome based solely on a timeout, one page, search result absence, or a failed API lookup.
6. Re-read `GET /publications/{publication_id}` after reconciliation and verify the stored status and audit evidence. If the record is not `unknown`, do not force a transition.

## API safety properties
- Both inspection and reconciliation require the Agent `X-API-Key`.
- Reconciliation is an explicit operator action; no background worker or automatic retry resolves `unknown`.
- Only `unknown` records may transition through this path.
- `succeeded` requires a non-empty verified Pin ID; `failed` forbids a Pin ID.
- No endpoint in this runbook publishes, deletes, edits, or creates a Pinterest Pin or board.

## Evidence gate for closing PB-07
Unit tests and the runbook establish a fail-closed mechanism, not a production incident rehearsal. Before marking the blocker fully closed, review the exact-head CI result after the code is reviewed/merged and run a disposable/test-account or provider-stub scenario proving persisted `unknown` -> retry blocked -> read-only board verification -> operator reconciliation -> verified final state. Never perform that scenario by publishing a real production Pin. If no isolated account/provider stub is available, keep PB-07 “implemented, isolated end-to-end verification pending.”
