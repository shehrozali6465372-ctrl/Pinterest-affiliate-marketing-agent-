# Affiliate Product URL Manager and 30-Day Scheduler

## Target behaviour
- Register up to 10 affiliate product sources for one schedule.
- Preserve each affiliate URL exactly as submitted, including tracking query parameters.
- Create a 30-day schedule with at most five scheduled slots per local calendar day (150 total slots).
- Store an IANA timezone and resolve each slot to an absolute timestamp.
- Select enabled sources fairly; do not assume one product should be posted five times daily.
- Persist one stable idempotency key per slot.
- Enforce a maximum of five successful publications per local day, including after retries or delayed worker invocations.
- Pause/cancel without deleting audit history.
- Treat uncertain Pinterest outcomes as reconciliation-required; never automatically retry an uncertain Pin create.
- Reuse the existing image/content generation and canonical publication-ledger path. No second direct Pinterest Pin writer.

## Scheduling runtime
Render Free web services can sleep, so an in-process timer is not dependable. Use an external GitHub Actions cron trigger to wake a protected worker endpoint. The worker must claim jobs transactionally with PostgreSQL row locking (FOR UPDATE SKIP LOCKED), enforce per-day success caps in the database, and remain idempotent when cron invocations overlap or arrive late. GitHub Actions cron is best-effort and may be delayed; exact-minute publication cannot be promised.

## Safety and activation
Creating the schema or deploying code must not create a schedule, board, or Pin. Schedules start as draft. Only an explicit activation action may enqueue jobs and enable publishing. Tests use mocked providers and isolated test PostgreSQL. Never call production Pinterest publish endpoints in tests.

## Milestones
- [x] Isolated feature branch created.
- [x] Additive queue schema migration drafted; no production data is seeded.
- [ ] Authenticated source and schedule management APIs.
- [ ] Transactional activation and deterministic 30-day job generation.
- [ ] Due-job claiming, bounded retries, uncertain-outcome reconciliation and daily success cap.
- [ ] External scheduled worker workflow.
- [ ] Isolated PostgreSQL and mocked-provider tests.
- [ ] PR and required CI checks.
- [ ] Keep production schedule inactive until product data is supplied and explicitly activated.


## Implemented on the feature branch

- Draft schedule API accepts 1–10 product sources and preserves affiliate URLs without rewriting tracking parameters.
- Draft schedule records account, IANA timezone, start date, duration (1–30 days), daily limit (1–5), and board metadata.
- Explicit activation transaction creates deterministic local-time slots at 09:00, 12:00, 15:00, 18:00, and 21:00 (limited by daily_pin_limit), converted to UTC. Product sources are assigned round-robin.
- Pause endpoint cancels queued jobs but retains history.
- Protected worker claims at most one due job per invocation using PostgreSQL row locking, invokes the existing product workflow, retries selected pre-publication 503 failures with bounded backoff, and quarantines uncertain outcomes rather than replaying them.
- Hourly GitHub Actions workflow invokes the protected worker. It is best-effort; posting can be delayed. It only processes jobs after an operator has activated a schedule.
- Tests cover source-count validation, timezone validation, tracking URL preservation, draft-only creation, and API-key enforcement.

## Verification boundary

These changes are on the feature branch only. CI has not yet run against this branch. No migration has been applied to production Neon, no production schedule has been created or activated, and no Pinterest board or Pin has been created.


## Deployment order (not executed)

1. Merge only after all required CI checks pass.
2. Deploy the Agent application.
3. Apply the additive schema explicitly with `python scripts/migrate.py` against the intended database. The application does not run migrations automatically at startup.
4. Verify the new tables using read-only SQL.
5. Verify authenticated schedule creation in draft mode with test data only.
6. Configure the GitHub Actions secret already used by the protected Agent workflows; verify the worker workflow while no active schedule exists.
7. Only then, after the owner supplies product URLs and explicitly authorizes activation, create and activate a production schedule.

The current PR does not run step 3, does not alter Render settings or GitHub secrets, and does not activate a schedule.

## Operational semantics

- Only one active schedule is permitted per Pinterest account, preventing overlapping schedules from bypassing the account-level five-per-day cap.
- A schedule cannot start on a past local calendar date. Its configured posting slots use the schedule's IANA timezone.
- Pause cancels queued work; a job already claimed and running may finish. The API response explicitly reports this.
- A missing/disabled product source is marked failed and the schedule is still eligible to complete.
