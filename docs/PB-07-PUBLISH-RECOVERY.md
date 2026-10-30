# PB-07 — Safe publication recovery runbook

## Safety rule
Never retry a publication in `pending` or `unknown`. A timed-out POST may have created a Pin. Do not induce an ambiguous publish in production to test recovery.

## Inspect a publication record
Call `GET /publications/{publication_id}` with the configured `X-API-Key`. This is database-only; it does not call Pinterest. Verify publication ID, account ID, board ID, content version ID, status, and last update. Do not include access tokens in evidence or support messages.

## Verify uncertain outcomes (read-only)
1. Call the protected Agent endpoint `GET /publications/{publication_id}/pinterest-verification` with `X-API-Key`. The Agent decrypts the connected account credential in process memory, lists every page of the exact stored board using Pinterest `GET /v5/boards/{board_id}/pins?page_size=250`, and returns sanitized Pin fields. It never returns the token.
2. The endpoint follows every pagination `bookmark` until null, rejects repeated/malformed bookmarks, and fails the request if any page errors or the 100-page safety bound is reached. Only `pagination_complete=true` is acceptable evidence. If the response errors or permissions are insufficient, stop: keep the row `unknown` and do not retry.
3. If the publication already stores a Pin ID, the Agent also calls `GET /v5/pins/{pin_id}` and reports whether the Pin appears in the exact board listing and whether the detail response confirms the same Pin and board. For an `unknown` row with no stored Pin ID, compare the returned title, description, destination link, and creation-time window; do not rely on title alone. If more than one candidate matches, leave `unknown` and escalate for human review.
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
Unit tests and the runbook establish a fail-closed mechanism, not a production incident rehearsal. Review exact-head CI and run a provider-stub/disposable PostgreSQL scenario proving persisted `unknown` -> retry blocked -> complete read-only pagination -> operator reconciliation -> verified final state. Never perform that scenario by publishing a real production Pin. The protected verification endpoint can additionally inspect an existing succeeded publication without any write; this validates live account authorization, board pagination, and direct Pin lookup but does not simulate an unknown publication. If no isolated account/provider stub is available, retain the explicit limitation that real ambiguous-publication recovery was not rehearsed.
