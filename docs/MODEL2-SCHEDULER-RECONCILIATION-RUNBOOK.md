# Model 2 Scheduler Job Reconciliation Runbook

**Status:** Implemented and verified on the feature branch. This runbook is for operator recovery only; it does not activate the scheduler or publish Pins.

## Safety boundary

- Reconciliation is a database-only operation. The GET/POST endpoints do not call Pinterest, refresh OAuth, invoke the publishing workflow, generate content/media, or create a Board/Pin.
- Use only an exact account/job pair. The shared `X-API-Key` authenticates the service request; `account_id` is checked against the job's persisted schedule account. The shared key does **not** identify an individual human operator, and the current audit row is not a cryptographic/non-repudiable human identity record. Do not claim otherwise.
- Do not guess whether a Pin exists. A success requires a confirmed Pin ID and exactly one matching publication-ledger row. A failure requires explicit confirmation that the Pin is absent.
- Never put OAuth tokens, API keys, cookies, or other credentials in `operator_evidence`.
- A reconciled `failed` job is terminal. Do not requeue it or reuse its idempotency key. A future attempt must be a separate approved job with a new key.

## 1. Inspect without changing state

Set the service base URL, operator API key, account ID and job ID in your trusted shell environment. Do not paste secrets into source control or this document.

```bash
curl --fail-with-body --silent --show-error \
  -H "X-API-Key: $APP_API_KEY" \
  "$BASE_URL/affiliate-scheduler/jobs/$JOB_ID/reconciliation?account_id=$ACCOUNT_ID"
```

The response is read-only and includes the job state, account/niche, number of publication candidates, a safe linkage status and (only when uniquely matched) the publication ID/status, board ID and Pin ID.

Interpret `linkage_status` as follows:

- `matched`: exactly one publication row matches the idempotency key, account and applicable niche attribution.
- `no_publication_candidate`: no publication row is linked to the key.
- `ambiguous_publication_candidates`: more than one candidate exists; stop and investigate manually.
- `publication_account_mismatch`, `publication_product_mismatch`, or niche mismatch: stop; do not reconcile by overriding the mismatch.

## 2. Reconcile a confirmed successful publication

Only proceed when the operator has independently verified the exact Pin ID on the expected Pinterest account/Board. The ledger must contain exactly one matching publication candidate. Do not use a guessed ID.

```bash
curl --fail-with-body --silent --show-error \
  -X POST \
  -H "X-API-Key: $APP_API_KEY" \
  -H "Content-Type: application/json" \
  "$BASE_URL/affiliate-scheduler/jobs/$JOB_ID/reconcile" \
  -d '{
    "account_id": "pinterest:REPLACE_WITH_ACCOUNT_ID",
    "outcome": "succeeded",
    "pinterest_pin_id": "REPLACE_WITH_VERIFIED_PIN_ID",
    "operator_evidence": "Verified exact Pin ID and expected account/Board using the operator evidence record.",
    "confirm_pin_absent": false
  }'
```

A unique `unknown` publication may be reconciled immediately with evidence. A `pending` publication must be at least ten minutes old. If the ledger already says `succeeded`, the supplied Pin ID must exactly match its stored ID. A missing ledger row cannot be marked successful.

## 3. Reconcile a confirmed absent publication

Only proceed after the operator has checked the exact account and expected Board and confirmed that the Pin is absent. This requires explicit `confirm_pin_absent: true`; omit `pinterest_pin_id`.

```bash
curl --fail-with-body --silent --show-error \
  -X POST \
  -H "X-API-Key: $APP_API_KEY" \
  -H "Content-Type: application/json" \
  "$BASE_URL/affiliate-scheduler/jobs/$JOB_ID/reconcile" \
  -d '{
    "account_id": "pinterest:REPLACE_WITH_ACCOUNT_ID",
    "outcome": "failed",
    "operator_evidence": "Checked the exact account and expected Board; confirmed the Pin is absent.",
    "confirm_pin_absent": true
  }'
```

This records the job as terminal `failed`. If a publication ledger row exists, it is also marked `failed`; if none exists, the audit row records a null publication ID. Do not replay the original scheduler job.

## 4. Atomicity and audit

The publication ledger update (when present), scheduler-job state transition and append-only audit row are committed in one PostgreSQL transaction. Any failure rolls the whole transaction back. The audit stores account, schedule/job/publication IDs, outcome, optional Pin ID, operator evidence and timestamp. It does not store credentials. Treat `operator_evidence` as a short reference/summary only; never paste secrets, tokens, cookies, raw headers or sensitive personal data. UPDATE, DELETE and TRUNCATE are rejected by database triggers under ordinary SQL access; a database owner/superuser can still alter or disable triggers, so this is not tamper-proof against privileged DB administrators.

The endpoint returns HTTP 409 for non-uncertain jobs, ambiguous/mismatched linkage, a recent pending publication, insufficient evidence or conflicting ledger state. Stop and investigate; do not try a different ID until the evidence is independently established.

## 5. Explicitly out of scope

- No scheduler activation or `/affiliate-scheduler/run-due` invocation.
- No live Pinterest publishing, Board creation, OAuth refresh, provider/media/content generation.
- No automatic retry or requeue with the same idempotency key.
- No production migration, deployment, PR, merge, or live schedule activation. Those remain separate release approvals.
