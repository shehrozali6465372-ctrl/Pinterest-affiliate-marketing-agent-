# Phase 10 — Scheduler Job Reconciliation Design

**Status:** Design review checkpoint — implementation and PostgreSQL verification pending.
**Scope:** Resolve an `affiliate_pin_jobs.status = 'uncertain'` job against the existing `pin_publications` ledger without sending Pinterest writes.

## 1. Existing contracts verified

- Scheduler jobs have a unique `idempotency_key`, optional `product_id` and `pinterest_pin_id`, and states `queued | processing | succeeded | failed | uncertain | cancelled` (migration 009).
- Products retain the workflow idempotency key. A publication is unique by `(content_version_id, board_id)` and stores account, outcome, Pin ID and response metadata (migrations 003 and 007).
- Model 2 publication attribution is immutable and keyed by publication/account/niche (migration 013).
- `reconcile_unknown_publication()` already resolves a `pin_publications` row after operator evidence, but it does not update the associated scheduler job.
- The generic publication reconciliation endpoint also does not establish a scheduler-job-to-publication relationship.
- The workflow rejects an already-persisted product idempotency key before reaching the publication gateway. Therefore, marking a scheduler job failed must NOT imply that the same job can safely be requeued with its old idempotency key.

## 2. Required invariants

1. Reconciliation is operator-authenticated and account-scoped.
2. Reconciliation never calls Pinterest, refreshes OAuth, generates media/content, or invokes the publishing workflow.
3. A job may be reconciled only from `uncertain`; a fresh `processing` job is not eligible.
4. Resolve the publication by the job's exact idempotency key, then verify product, schedule account, content version and (for Model 2) immutable niche attribution.
5. Zero or multiple candidate publication rows are not silently guessed. A successful outcome requires exactly one matching publication ledger row.
6. A publication already recorded as `succeeded` is positive evidence; its stored Pin ID may be copied to the scheduler job only when account/board/publication linkage is unambiguous.
7. For `unknown` or stale `pending` ledger rows, operator-supplied evidence is mandatory. `succeeded` requires a Pin ID. `failed` requires an explicit confirmation that the Pin is absent.
8. Update the publication ledger, scheduler job, and reconciliation audit record in one PostgreSQL transaction. If any write fails, all changes roll back.
9. A confirmed-absent job becomes terminal `failed`; do not requeue it with the same idempotency key. A future publication, if separately approved, must be a new scheduled job with a new idempotency key.
10. Missing ledger rows may be reconciled to terminal scheduler `failed` only with explicit operator evidence confirming absence. They cannot be reconciled to `succeeded` because no publication ID/board/content lineage exists to prove the claim.
11. Any mismatch, missing account attribution, multiple ledger candidates, stale-state race, or insufficient evidence leaves the job `uncertain`.
12. Reconciliation evidence is retained as an append-only audit record; never store access tokens or credentials in evidence.

## 3. Proposed API

- `GET /affiliate-scheduler/jobs/{job_id}/reconciliation`: read-only status and candidate-linkage summary. It must not query Pinterest.
- `POST /affiliate-scheduler/jobs/{job_id}/reconcile`: accepts `outcome`, optional `pinterest_pin_id`, and bounded nonblank `operator_evidence`.

Response fields must be minimal: job ID/status, schedule/account identifiers, ledger publication ID/status (if uniquely found), and whether the operation was read-only/reconciled. Never return affiliate URLs, product details, OAuth data, or secrets.

## 4. Transaction and locking

- Use the same account/profile → niche → assignment → schedule → job lock order used by the Model 2 scheduler.
- Lock the schedule and target job; verify the job remains `uncertain`.
- Resolve all publication candidates from the persisted product idempotency key and verify account and immutable niche attribution.
- Lock the unique publication row before changing it.
- Enforce the existing ten-minute minimum for stale `pending` publications. An `unknown` publication can be reconciled immediately with evidence.
- Write the immutable audit record, update ledger state when one exists, update scheduler job state and Pin ID, then re-evaluate schedule completion before commit.
- Use one transaction; do not call the existing standalone reconciliation function from inside this transaction because it opens its own connection and would break atomicity.

## 5. Explicit non-goals

- No automated Pinterest search to infer absence.
- No automatic retries or queue replay.
- No live worker dispatch, schedule activation, production migration, deployment, PR, merge, or real Pin/Board creation.
- No changes to legacy Model 1 quota semantics.

## 6. Required PostgreSQL regression matrix

All cases must use synthetic fixtures in disposable PostgreSQL; no real Pinterest writes.

| Case | Expected result |
|---|---|
| Unique unknown ledger + verified Pin ID | Ledger and job become succeeded; audit committed |
| Unique stale pending ledger + verified Pin ID | Both become succeeded |
| Unique unknown ledger + confirmed absence | Ledger and job become failed; audit committed |
| No ledger + confirmed absence | Job becomes failed; audit committed with null publication |
| No ledger + claimed success | Reject; job remains uncertain |
| Multiple publication candidates | Reject; no rows changed |
| Account mismatch | Reject; no rows changed |
| Model 2 niche attribution missing/mismatch | Reject; no rows changed |
| Pending ledger younger than ten minutes | Reject; no rows changed |
| Blank/oversized evidence or missing Pin ID | Reject at validation; no rows changed |
| Job not uncertain | Reject; no rows changed |
| Audit/ledger/job write failure | Entire transaction rolls back |
| Repeated reconciliation | Conflict; no second audit or state mutation |
| Confirmed absence | No same-key requeue; later independent job uses a fresh key |
| Read-only inspection | No Pinterest/provider call and no DB mutation |
| Legacy Model 1 job | Account linkage works without requiring Model 2 niche attribution |

CI must explicitly include the new reconciliation tests, verify all numbered migrations are recorded, verify audit fixtures are cleaned, and stop the disposable PostgreSQL service. Exact-head CI is the acceptance gate; local mocked tests alone are insufficient.

## 7. Release gate

This design is not an implementation or a production approval. Phase 10 remains blocked until the transaction, API, audit migration, regression matrix, exact-head CI, migration/restore rehearsal and separate owner approvals are complete.
