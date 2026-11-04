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
