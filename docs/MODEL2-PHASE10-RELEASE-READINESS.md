# Model 2 Phase 10 — Release Readiness

**Status:** PRE-RELEASE REVIEW — NOT APPROVED FOR PRODUCTION RELEASE. R1 hardening is implemented locally; exact-head CI is pending.

**Review date:** 2026-11-09  
**Feature branch:** `feat/model2-open-source-reuse`  
**Base production snapshot:** `785efd99849627062c1fff8504d21ca91abfee8e`

## 1. Scope and hard boundaries

This is a static/security and disposable-CI release-readiness review only. It does not authorize:

- applying migration 014 to Neon or any shared/production database;
- deploying or merging Model 2;
- activating schedules, running due jobs, or invoking the scheduled worker against production;
- Pinterest API writes, OAuth refresh/reconnect/token rotation, or real Pin/Board creation;
- PR creation, merge, promotion or deployment.

No production credentials or database contents were read for this review.

## 2. Verified release evidence

- Phase 9 owner-approved implementation is on the isolated feature branch.
- Exact implementation CI commit `761204b7e5d09cce6eb5f26543602702d5db606a`, run `42536328716`: **212 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15.
- Docs closure commit `14e8e97c08fb1f61d93cf969e08cfe4cf9e9eb1d`, run `42536572870`: **212 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15.
- Both runs recorded all 15 numbered migrations, verified Model 2 and synthetic Model 1 fixture cleanup, and stopped the ephemeral PostgreSQL container.
- Local full suite at the implementation checkpoint: **283 passed, 56 skipped, 1 non-blocking warning**. Local DB integration tests were skipped because `DATABASE_URL` and `TEST_DATABASE_URL` were unset. CI is the PostgreSQL evidence.
- Feature branch is isolated from `main`; no PR/merge/deploy.

## 3. Security and operational findings

### R1 — Uncertain publication must consume quota and block replacement

**Severity:** High — release blocker.  
**Status:** Fix implemented; exact-head CI pending.

A scheduler job in `uncertain` may correspond to a Pin that Pinterest created even though the response was lost or ambiguous. Before hardening, account quota counted only `processing` and `succeeded`, and schedule replacement only blocked `queued`/`processing`. This could permit another Pin after an ambiguous result.

Hardening in this review:
- Model 2 account-local quota counts `uncertain` alongside `processing` and `succeeded`.
- An unresolved uncertain job blocks replacement of the account schedule, including on a later local day.
- A schedule with an uncertain job is not automatically marked completed.
- Existing legacy Model 1 quota behavior is not changed.
- Regression coverage verifies the uncertain result is never re-run, consumes the daily quota, and blocks replacement.
- Local full suite after this hardening: **283 passed, 57 skipped, 1 non-blocking warning**. PostgreSQL integration tests remain skipped locally because DB environment variables are unset; no DB was contacted. Exact-head disposable PostgreSQL CI is the next gate.

**Remaining operational limitation:** there is no scheduler-job reconciliation endpoint in this phase. An uncertain job therefore remains fail-closed until an operator follows a separately approved, evidence-based reconciliation procedure. Do not directly edit production job status or infer that a Pin does not exist. A documented and tested reconciliation/runbook path is required before enabling unattended Model 2 scheduling.

### R2 — Scheduled worker is a production side-effect trigger

**Severity:** High — release gate.

`.github/workflows/affiliate-scheduler-worker.yml` contains an hourly GitHub Actions cron and calls the deployed Render `/affiliate-scheduler/run-due` endpoint with the service API key. It can execute queued jobs and publish Pins through the existing workflow. This review did not run or alter that workflow.

Before production release, the owner must explicitly approve when Model 2 schedules may be created/activated and when the worker may execute them. Do not use a live workflow dispatch as a test. Existing Model 1 scheduled behavior must be preserved and separately accounted for.

### R3 — Production migration rehearsal and rollback plan

**Severity:** High — release gate.

Migration 014 is additive: nullable `niche_id`, composite FK, indexes and a trigger scoped to Model 2 schedule rows. Disposable CI applied all numbered migrations from a clean PostgreSQL 16 database. This is not a rehearsal against a sanitized production-like snapshot.

Proposed release procedure (not executed):
1. Capture and verify a restorable backup/snapshot using the approved database operations process.
2. Rehearse migration 014 against a sanitized clone with production-like schema and representative legacy schedules/jobs.
3. Verify legacy schedules retain `niche_id IS NULL`, remain readable/updatable under legacy behavior, and no existing rows are backfilled or rewritten.
4. Verify Model 2 constraints, indexes and trigger; run read-only post-migration integrity checks.
5. Deploy application code only after migration rehearsal and explicit approval.
6. Rollback application code first if required; leave the additive schema in place. Do not drop migration 014 objects if Model 2 schedule rows may exist. Schema rollback requires a separately designed data-preserving procedure.

No production/shared DB migration or backup operation was performed.

### R4 — Shared API key is service authentication, not human identity

**Severity:** Medium — accepted architecture constraint.

Model 2 registry/learning and scheduler routes use the existing fail-closed service API key. The system is intentionally one owner/operator, not a multi-tenant identity platform. The key must be protected as a high-privilege service credential, and logs/UI must not expose it. Do not claim human actor attribution or tenant isolation.

### R5 — Scheduler timing is best-effort

**Severity:** Medium — operational constraint.

The worker workflow is hourly and GitHub Actions cron may be delayed. It processes at most one due job per invocation. This is not a precise real-time scheduler. Release materials must communicate best-effort timing and ensure backlog behavior/rate limits are acceptable before activation.

### R6 — Non-blocking CI maintenance warnings

**Severity:** Low.

Current CI emits a Starlette/httpx TestClient deprecation warning and GitHub Actions Node.js 20 / `ubuntu-latest` migration warnings. They did not fail CI. Track dependency/action updates separately; do not change dependencies solely to silence warnings without compatibility tests.

## 4. Migration compatibility / rollback assessment

- Migration 014 adds a nullable column, FK, check, indexes and trigger; no table rebuild or data backfill is present.
- Existing Model 1 schedules keep `niche_id NULL`; trigger logic explicitly skips legacy rows.
- Existing one-active-schedule-per-account unique index is retained.
- Application rollback can leave the additive schema installed; old code does not need to read `niche_id` to use its existing explicit-column queries.
- Dropping the migration is not an approved rollback strategy. If Model 2 data exists, dropping FK/trigger/column risks losing or invalidating state.
- Production-like migration rehearsal and restore test remain unverified.

## 5. Release scorecard

| Area | Assessment | Evidence / gap |
|---|---|---|
| Account isolation | Pass in tests | Exact account+niche composite FK and repository/workflow checks |
| Authentication | Pass for service-key model | Fail-closed shared API key; no human/tenant identity |
| Publication safety | Conditional | Single gateway, idempotency and uncertainty quarantine; scheduler uncertainty reconciliation runbook missing |
| Quota concurrency | Pass in CI | Same-account serialization; different-account parallel claims; uncertain quota hardening awaits CI |
| Legacy compatibility | Pass in CI | Nullable niche, unchanged legacy branch, regression suite |
| Migration integrity | Pass in disposable CI | All 15 migrations applied; production-like rehearsal not run |
| Rollback | Partial | App rollback can retain additive schema; data-preserving schema rollback/restore not rehearsed |
| Operations | Conditional | Hourly best-effort worker can publish; explicit enablement/runbook needed |
| Observability | Partial | Safe job/schedule state available; operator reconciliation workflow and alerting policy need definition |
| Deployment | Not approved | No PR, merge, production migration or deployment authorized |

## 6. Exit criteria before any release approval

- [ ] Exact-head CI passes after R1 hardening; migration ledger and fixture cleanup verified.
- [ ] Operator reconciliation procedure for uncertain scheduler jobs is documented and tested without a real Pin write.
- [ ] Production-like sanitized migration rehearsal and restore/rollback rehearsal pass.
- [ ] Owner reviews the scheduled worker's production side effects and explicitly approves activation window/controls.
- [ ] Security review confirms service key handling, account scoping, log redaction and operational access.
- [ ] Owner explicitly approves production migration, deployment, and any scheduler activation as separate actions.

**Phase 10 status remains PRE-RELEASE / BLOCKED.** Passing disposable CI is not production readiness, migration approval, deployment approval or authorization to publish Pins.
