# Model 2 Phase 9 — Account-aware Scheduling Design

**Status:** DESIGN DRAFT — implementation not started.
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

Required changes in a future implementation:
- Count processing/succeeded jobs across all schedules for the same account, not only the current schedule.
- For quota day, use the actual claim/completion timestamp (locked_at for processing, finished_at for succeeded) converted to the account profile timezone. Fall back to run_at only for defensive handling of legacy rows with missing event timestamps.
- Keep the active schedule's configured daily_pin_limit as the account's current cap. Prior successful/processing jobs from earlier schedules on the same account-local day count against it.
- During activation, lock the account profile and schedule in a deterministic order; reject activation while any prior schedule for that account has a processing job. Paused schedule's queued jobs must already be cancelled. This prevents an old in-flight publish from overlapping a new schedule.
- During job claim, serialize claim/quota evaluation per account using the account profile row lock (or a reviewed transaction-scoped advisory lock keyed by canonical account_id), then lock the selected schedule/job. Define one global lock order and test for deadlocks.
- FOR UPDATE SKIP LOCKED remains for job distribution, but it is not by itself an account-level quota lock.
- A worker crash with an unknown Pinterest outcome remains uncertain; never auto-replay it. Operator reconciliation remains required.
- Retry keeps the same job idempotency_key. No new job/key is generated for a retry.
- If concurrent multi-niche schedules are required later, do not remove the one-active-schedule-per-account guard casually. Design a shared account quota/locking mechanism first and prove it with concurrent PostgreSQL tests.

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

## 7. Exit gate

Phase 9 remains IN PROGRESS until the owner accepts the one-active-schedule-per-account baseline (or explicitly requests the concurrent multi-niche alternative), and the adversarial test plan is reviewed. Only then may implementation be proposed. No live scheduler execution, production migration, provider/OAuth action, real Pin/Board, PR, merge or deployment is authorized.
