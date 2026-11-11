# Model 2 Phase 9 — Account-aware Scheduling Design

**Status:** COMPLETE — owner-approved implementation and exact-head disposable PostgreSQL CI verified on 2026-11-09.
**Date:** 2026-11-09
**Architecture authority:** docs/MODEL2-FOUNDATION.md (FROZEN)
**Prerequisites:** Phases 6, 7 and 8 closed.
**Safety:** No live scheduler activation, queue execution, Pinterest write, OAuth action, production DB migration or deployment is authorized.

## 1. Existing scheduler facts

- Scheduler implementation: app/affiliate_scheduler.py.
- Schema: migrations/009_affiliate_product_scheduler.sql.
- Existing tables: affiliate_publishing_schedules, affiliate_product_sources, affiliate_pin_jobs.
- Schedule stores account_id, timezone, dates, daily_pin_limit (1–5), board_name/description and status.
- One active schedule per account is enforced by affiliate_one_active_schedule_per_account_idx.
- One job per schedule/local date/daily slot is enforced by UNIQUE(schedule_id, local_run_date, daily_slot).
- Each job has a unique persisted idempotency_key. It is created at activation and reused for retries.
- Activation enqueues jobs only; it does not publish or contact Pinterest.
- Worker claims at most one due job with FOR UPDATE SKIP LOCKED; stale processing jobs become uncertain after 15 minutes rather than being replayed.
- Worker calls the existing publish_product_end_to_end workflow and canonical publishing gateway.
- Current worker passes account_id and board_name, but does not pass niche_id into ProductWorkflowInput.
- ProductWorkflowInput now supports optional niche_id; Phase 6 already validates exact active account+niche context before provider work and reserves immutable attribution through the existing gateway.
- Existing worker daily cap counts processing/succeeded jobs only within the same schedule and local_run_date. It does not enforce a cross-schedule account-wide daily cap.
- Existing schedule timezone is independently selected and can differ between schedules. Model 2 account profile already has a canonical timezone field.
- Scheduler account_id validation currently checks nonblank text, not canonical Pinterest account ID or Model 2 assignment.
- Existing workflow resolves a board by name against the connected account's board list and never creates a Board.

## 2. Recommended first Model 2 scheduling contract

**Keep the existing one-active-schedule-per-account rule.** An account may have multiple niche assignments, but only one active schedule (and therefore one active scheduled niche) at a time in the first safe release.

- A Model 2 schedule must carry an explicit niche_id. Never silently choose the primary niche.
- A legacy Model 1 schedule with niche_id NULL remains supported and preserves current behavior.
- Model 2 schedule account_id+niche_id must reference an exact existing model2_account_niches mapping; no inferred mapping.
- At draft creation and activation, require active account profile, active assignment, active niche and connected credential metadata. Use metadata-only credential checks; never decrypt or refresh tokens as part of schedule setup.
- Model 2 schedule timezone must equal the account profile timezone. The account profile is the canonical account-local quota clock.
- Keep the existing daily_pin_limit bounds (1–5) and existing one-active-schedule-per-account partial unique index.
- Board remains an explicit board_name resolved against the connected account's existing boards during execution. Missing/renamed board fails safely before publication. Never create Boards. Board-ID persistence can be a later separately reviewed change if board rename stability proves necessary.
- At execution, pass the schedule's exact niche_id into ProductWorkflowInput. The existing workflow revalidates the account+niche context before generation and the existing gateway writes immutable attribution atomically before Pinterest POST.
- A schedule's account_id, niche_id, timezone, board_name, date window and daily limit become immutable once activated. Pause/cancel does not rewrite historical jobs or publication attribution.

## 3. Account-level daily quota and schedule transition safety

The current per-schedule count is insufficient if a paused/completed schedule is replaced by another schedule on the same account during the same account-local day.

Implementation contract (now being implemented):
- Count processing/succeeded jobs across all schedules for the same account, not only the current schedule.
- For quota day, use the actual claim/completion timestamp (`locked_at` for processing, `finished_at` for succeeded), with `run_at` fallback for missing event timestamps. Compare timestamps against DST-aware account-local day bounds from the locked account profile timezone.
- Keep the active schedule's configured `daily_pin_limit` as the account's current cap. Prior successful/processing jobs from earlier schedules on the same account-local day count against it.
- During activation, lock the account profile, niche, assignment, schedule and then jobs in a deterministic order; reject activation while another schedule has queued/processing jobs. Pausing cancels queued jobs; in-flight jobs must become terminal before replacement.
- During job candidate selection, lock the eligible account profile with `FOR UPDATE SKIP LOCKED` before niche/assignment/schedule/job rows. This serializes quota evaluation for the same account while allowing another worker to select a different unlocked account rather than waiting behind it.
- `FOR UPDATE SKIP LOCKED` remains for job distribution, but is not treated as the account-level quota lock.
- A worker crash with an unknown Pinterest outcome remains uncertain; never auto-replay it. Model 2 treats uncertain as quota-consuming and blocks schedule replacement/automatic completion until operator reconciliation. No automated reconciliation transition is provided by this phase.
- Retry keeps the same job `idempotency_key`. No new job/key is generated for a retry.
- The first release remains one active schedule per account; concurrent multi-niche schedules are explicitly deferred.

## 4. Migration and compatibility boundary (future only)

A future additive migration may:
- Add nullable niche_id to affiliate_publishing_schedules.
- Add a composite FK (account_id, niche_id) to model2_account_niches. NULL niche_id preserves legacy Model 1 schedules.
- Add constraints/trigger rules preventing niche_id, account_id, timezone, board target or quota changes after activation.
- Add a suitable index for account-wide job quota queries.
- Preserve existing schedule/job rows exactly; no inferred niche backfill.
- Keep the existing one-active-schedule-per-account unique index.

No migration is part of this design phase. Production migration is a separate approval.

## 5. Adversarial test matrix required before implementation approval

1. Unknown/noncanonical account ID cannot create a Model 2 draft.
2. Account profile paused, niche archived, assignment paused or missing mapping blocks activation before jobs are inserted.
3. Disconnected credential metadata blocks activation; token value is never read/decrypted/refreshed by schedule setup.
4. No explicit niche_id means legacy Model 1 behavior only; Model 2 never falls back to primary niche implicitly.
5. Account A cannot schedule using account B's niche ID.
6. Two active schedules for one account cannot coexist, including different niches.
7. Replacing a paused schedule while an old job is processing is rejected until the in-flight job becomes terminal.
8. A prior succeeded job from a completed schedule counts toward the new schedule's same-day account quota.
9. Concurrent workers cannot claim jobs whose combined processing+succeeded count exceeds the account daily cap.
10. Different account IDs do not block each other's quota or job claims.
11. Account profile timezone is canonical; schedule timezone mismatch is rejected. Include DST boundary and local-date conversion cases.
12. Retry uses the same job idempotency key and cannot change niche attribution.
13. An uncertain publication remains quarantined and is never automatically retried.
14. Missing/renamed board fails before Pinterest POST; no Board creation route is called.
15. Existing legacy schedule with niche_id NULL still calls the existing workflow without niche context.
16. Model 2 scheduled workflow passes exact niche_id; gateway stores exact attribution before provider POST.
17. Worker/activation lock ordering has no deadlock under concurrent account activity.
18. Existing Model 1 scheduler regression suite passes unchanged for legacy schedules.

All tests must use mocks or a disposable PostgreSQL database. Never publish a real Pin or create a real Board.

## 6. Deferred design decision

The safe first release intentionally supports only one active schedule per Pinterest account, with one explicitly selected niche per schedule. It does not schedule multiple niches concurrently on one account.

If simultaneous multi-niche schedules are a hard requirement, that is a material change to account quota semantics and needs a separate owner-approved design before implementation.

## 7. Owner decision — accepted 2026-11-09

The owner explicitly approved the recommended baseline: **one active schedule per Pinterest account, with one explicit niche per Model 2 schedule**. Multiple niche assignments remain supported, but concurrent active niche schedules on one account are deferred.

## 8. Implementation checkpoint — 2026-11-09

- Added migration 014 with nullable niche attribution, composite account+niche FK, canonical Model 2 account-ID constraint, quota indexes and activated-schedule configuration immutability trigger.
- Extended `CreateScheduleInput` with optional strict positive `niche_id`. A Model 2 schedule requires an exact active account profile, assignment and niche; connected credential state is checked using `pinterest_credentials.status` only. No token/ciphertext is selected, decrypted or refreshed.
- Enforced schedule timezone equality with the Model 2 account profile timezone at draft creation and activation.
- Activation revalidates all Model 2 context, rejects replacement while a previous schedule has queued/processing jobs, and retains the existing one-active-schedule-per-account index. Pause cancels queued jobs and leaves in-flight work visible.
- Worker passes the exact schedule niche into the existing `ProductWorkflowInput`; the existing workflow revalidates it and the existing publishing gateway remains the only publisher.
- Account quota counts processing/succeeded jobs across all schedules for the same account using actual claim/completion timestamps, with `run_at` fallback. Account-local day boundaries are timezone-aware and DST-aware. Account profile row lock serializes Model 2 worker quota evaluation before schedule/job locking. Legacy NULL-niche schedules retain their existing per-schedule/local-date quota path.
- Added PostgreSQL integration tests for exact account+niche binding, timezone mismatch, paused assignment, revoked credential metadata, processing-job replacement guard, cross-schedule quota by event timestamp, exact niche pass-through, activated configuration immutability, same-account concurrent quota serialization, independent different-account worker claims, retry idempotency-key preservation and uncertain-outcome quarantine. Added DST unit tests and retained Model 1 scheduler regression tests.
- Final concurrency review changed Model 2 candidate discovery to lock the account profile with `FOR UPDATE SKIP LOCKED` directly in the candidate query. This prevents two workers from both selecting the same earliest account and causing the second worker to return `no_due_job` while another account is available. The exact account profile remains the quota serialization key.
- Added scheduler tests to the dedicated disposable PostgreSQL GitHub Actions workflow and static migration contract tests.
- Local focused tests: **17 passed, 38 skipped, 1 non-blocking warning**. The skipped tests include PostgreSQL integration cases because `TEST_DATABASE_URL` is unset locally; no database was contacted. Full local repository suite: **283 passed, 56 skipped, 1 non-blocking warning**. PostgreSQL integration tests skipped because DB environment variables are unset; no DB was contacted. Python compilation and `git diff --check` pass at this checkpoint.
- First exact-head CI run on commit `8c675c7` passed **210 tests, 0 failed, 1 warning** against disposable PostgreSQL 16.15; all 15 migrations were recorded, Model 2/synthetic Model 1 fixtures were cleaned, and the PostgreSQL container was stopped. Run: `42536015181`.
- Final concurrency/retry/quarantine follow-up is commit `761204b7e5d09cce6eb5f26543602702d5db606a`. Exact-head GitHub Actions run `42536328716` passed **212 tests, 0 failed, 1 warning** against disposable PostgreSQL 16.15. It verified all 15 numbered migrations, zero remaining Model 2 and synthetic Model 1 fixture rows, and completed the `Stop containers` job successfully.
- Final adversarial coverage proves: same-account concurrent workers cannot exceed the account-local daily quota; different accounts can be claimed concurrently; retry preserves the original idempotency key; uncertain publication outcome is quarantined and never blindly replayed; exact niche is passed through; replacement waits for in-flight work; DST-aware day boundaries are 23/25 hours on transition days; and activated Model 2 schedule configuration is database-immutable.
- Subsequent Phase 10 review identified an additional conservative release-hardening case: an unresolved `uncertain` outcome must consume quota and block schedule replacement, even after the original local day. This is being tracked and verified under `docs/MODEL2-PHASE10-RELEASE-READINESS.md`; it does not retroactively invalidate the Phase 9 implementation gate, but unattended release remains blocked until verified.
- Local full repository suite at final code checkpoint: **283 passed, 56 skipped, 1 non-blocking warning**. The 56 skips include PostgreSQL tests because local DB environment variables are unset; no local or production database was contacted. PostgreSQL proof comes from the dedicated CI run above.

No live scheduler activation or queue execution, production/shared DB migration, provider/OAuth action, real Pin/Board, PR, merge or deployment is authorized. No actual Pinterest publishing call is made by the tests; workflow calls are mocked.

## 9. Exit gate — CLOSED 2026-11-09

All Phase 9 implementation gates passed on exact feature-branch head `761204b7e5d09cce6eb5f26543602702d5db606a`:
- Dedicated PostgreSQL 16.15 GitHub Actions run `42536328716`: **212 passed, 0 failed, 1 non-blocking warning**.
- All 15 numbered migrations applied and recorded in the disposable CI database.
- Model 2 and synthetic Model 1 test fixtures verified cleaned; ephemeral PostgreSQL container stopped.
- Same-account quota serialization, different-account parallelism, retry-key preservation, uncertain-outcome quarantine, assignment/context validation, schedule immutability and DST behavior are covered by passing tests.
- Local full suite: **283 passed, 56 skipped, 1 warning**; local DB integration skips are not counted as PostgreSQL evidence.

**Phase 9 is formally CLOSED for implementation and isolated feature-branch verification.** This does not authorize production/shared DB migration, live scheduler activation/execution, provider/OAuth actions, real Pin/Board, PR creation, merge or deployment. Each remains a separate owner approval.
