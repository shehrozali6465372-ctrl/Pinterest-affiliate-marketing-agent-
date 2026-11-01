# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Audit refresh: 2026-11-01
Mode: READ-ONLY SOURCE REVIEW AND DOCUMENTATION. No application source, database, secrets, provider state, production service, deployment or Pinterest Pins were changed.

## Scope verified from current GitHub tree

- Python files: 30 total — app 12, scripts 1, tests 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Existing audit Markdown artefacts before this refresh: 90 excluding index.
- New audit records added in this refresh: 5.
- Record/file count is not the number of definitions fully audited and is not a completion percentage.

Note: current repository tree inspection enumerated 17 test modules (not 13); all 17 test files need per-test-function inventory. The prior index statement that 17 modules were scanned is a count, not proof that every test helper/function had a separate audit record.

## Newly added records in this refresh

- `FN-APP-CONFIG-PY-003`: settings singleton and module construction.
- `FN-APP-PINTEREST-PY-001`: PinterestPublishError.
- `FN-APP-PINTEREST-PY-002`: PinterestReadError (provisional source line coordinates).
- `FN-APP-LEARNING-PY-005`: learning router and metric constants.
- `FN-APP-PINTEREST-PY-005`: read-error class record (overlaps semantically with PY-002 and must be consolidated; do not count both as independent definitions).

## Material source findings

1. `app/learning.py::run_learning_loop` selects only successful publications having a Pin ID and matching account_id, requests the four listed analytics metrics, validates and persists snapshots, and returns `model_trained: false`. This is real analytics ingestion/evaluation logic, not a predictive ML training implementation.
2. The Learning Loop route obtains a stored credential and sends its access token directly in the analytics GET request. This function does not itself call the token-refresh function. Whether expiry is refreshed elsewhere must be established by full call graph; treat this as a potential expiry-handling gap until verified.
3. `pinterest-learning-loop.yml` schedules a daily endpoint invocation (03:17 UTC) and uses the app API key as a GitHub secret. The workflow validates account ID format, suppresses secrets from output, and prints a bounded summary.
4. `read-only-production-verification.yml` contains only GET verification calls; `safe-production-diagnostics.yml` invokes the protected diagnostics POST and checks the returned side-effect contract. That diagnostic may consume provider credits even though it does not create a Pin; workflow code explicitly allows provider usage may be billable.
5. `ci.yml` runs pytest with Python 3.11 and a PostgreSQL service; `tests.yml` runs pytest with Python 3.12 without a PostgreSQL service environment. These are separate workflows with potentially different coverage/runtime behavior.
6. SQL migration 003 enforces successful publications have a Pin ID and uniqueness by content_version_id + board_id. Migration 007 adds nullable account_id; legacy rows intentionally remain unassigned. Migration 006 deduplicates snapshots by Pin ID and period.
7. Migration 001 originally sets products.image_url NOT NULL; migration 008 later drops NOT NULL. This is a deliberate schema evolution, not an inconsistent final state.
8. Pinterest write helper attaches affiliate URL in the ordinary Pin `link` field. This is not evidence of Pinterest native product-tag API usage.
9. No dedicated product-research/extraction endpoint has been demonstrated by this audit scope. The publishing workflow accepts product name/details/affiliate URL as input; do not assert automated Amazon catalog discovery exists without source evidence.

## CI evidence seen

GitHub Actions returned a completed successful `Python tests` run for commit `ccb52f81e38ceda28a984855292c0f0dc47eec76` on 2026-11-01. This proves that specific workflow run succeeded; it does not prove live Pinterest, Neon, Cloudflare or DeepSeek behavior. This status belongs to that commit, not necessarily current HEAD after this documentation refresh.

## Record quality issues discovered

- At least two pairs of files had duplicate-looking IDs/near-duplicate slugs in the existing records, including the content-generation safe-failure metadata and main serialize-row records.
- Pinterest read-error records added in this refresh overlap; consolidate to one canonical definition record.
- Several earlier records are preliminary or use stale source snapshots/line ranges. They must be fetched and compared to current main before sign-off.
- Some class/model records are not Python functions but still count as source definitions and need consistent type labelling.
- Existing record list should be machine-generated from the live tree only after duplicate IDs are resolved.

## Verification vocabulary

- VERIFIED — SOURCE RETRIEVED: exact current source fetched.
- VERIFIED — DEFINITION ISOLATION: one complete definition and exact boundaries checked.
- VERIFIED — STATIC LOGIC: relevant branches/callers traced.
- VERIFIED — ASSERTION MAPPING: tests inspected and mapped to behavior.
- VERIFIED — CI RUN: a named GitHub Actions run completed; not equivalent to external integration proof.
- VERIFIED — LIVE BEHAVIOR: only where an approved safe runtime check proves it.
- UNVERIFIED: incomplete or absent evidence.

## Remaining completion criteria

1. Generate exact AST-style definition inventory for all 30 Python files: classes, top-level and nested functions, async functions, validators, test functions and nested test helpers.
2. Give every definition exactly one unique record; remove duplicate IDs/records and normalize class/function naming.
3. Re-fetch every earlier source record, update stale line ranges and expand records to describe every branch, default, loop, DB query/write, external call, exception and return.
4. Map every test assertion to production behavior and distinguish mocked tests from actual disposable-PostgreSQL integration coverage. Obtain CI run/job details for all relevant workflows and current commits.
5. Audit all eight SQL migrations for constraints, indexes, transaction behavior, rollback/repeatability and data backfill implications.
6. Trace complete call graph for OAuth ingest/refresh/revoke, publication/idempotency/reconciliation, analytics, provider diagnostics, and image/content generation.
7. Inspect all five GitHub Actions workflows for permissions, triggers, schedule, secrets, timeouts, network operations, production effects and billing risk.
8. Reconcile README, architecture/context files, PB tracker and environment template against the current source tree.
9. Produce final function coverage matrix, test matrix, database/workflow matrix, call graph and prioritized risk register.

## Safety boundary

No publish-capable route, OAuth mutation, provider-generation operation, production database mutation, migration, deployment, merge or secret change is authorized by this audit. Do not execute the publish workflow during tests. If a production check could spend provider credits, require separate explicit approval.
