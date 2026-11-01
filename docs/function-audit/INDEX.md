# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Audit refresh: 2026-11-01
Application source baseline: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
Mode: READ-ONLY source review and documentation. No application code, production DB, credentials, provider state, deployment or Pinterest Pins changed.

## Current inventory

- Python files under app/, scripts/ and tests/: 30.
- Test modules: 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Audit Markdown files including this index: 141.
- Separate audit/review records excluding index: 140.
- Duplicate IDs detected in current audit filenames: 0.

These record counts are not a completion percentage. Some records are test-function reviews; some production definition records remain preliminary and require current-source line-range and nested-definition verification.

## Work completed in this continuation

- Re-enumerated all Python definition declarations across app/, scripts/ and tests/ using the current GitHub main source.
- Confirmed the 17 test modules and inspected their function/class declarations.
- Removed three duplicate/preliminary records and corrected the PinterestReadError record to exact source lines 60-61.
- Added isolated records for PinterestPublishError.__init__ and the nested content-generation sanitizer.
- Added individual test-function audit records for:
  - Base64 image source tests (3).
  - Read-only Pinterest tests (5).
  - Learning analytics tests (4).
  - Provider retry / Cloudflare retry tests (5).
  - Token refresh tests (6).
  - Publication state-machine tests (4).
  - Workflow persistence/recovery tests (5).
  - Publication reconciliation and read-only verification tests (14).

## Source-level findings retained

1. `app/learning.py::run_learning_loop` filters confirmed successful Pins by account, requests analytics, validates and persists snapshots, and explicitly returns `model_trained: false`. This is analytics ingestion/descriptive evaluation, not predictive ML training.
2. The Learning Loop obtains a stored access token and uses it for analytics GET calls. The function itself does not invoke token refresh. Automatic refresh on expiry is therefore not demonstrated by this route; verify the broader call path before deciding whether it is a defect.
3. The daily Learning Loop workflow calls the protected endpoint and suppresses secret values in output. It is an analytics ingestion trigger, not evidence that training occurs.
4. The read-only verification workflow uses GET requests. Safe diagnostics invoke a protected diagnostics POST and may consume provider credits; they are not Pin publishing.
5. CI workflow definitions use different Python versions and test database setup. A completed Python Tests run for commit `ccb52f81e38ceda28a984855292c0f0dc47eec76` on 2026-11-01 succeeded. This is evidence for that run only, not current production integration proof.
6. Migration 003 enforces successful publication records have a Pin ID and uniqueness by content_version_id + board_id. Migration 007 adds nullable account_id, leaving legacy rows unassigned. Migration 006 stores analytics snapshots unique by Pin and period.
7. The Pinterest write helper attaches the affiliate URL in the Pin `link` field. This is not evidence of native Pinterest Product Tag support.
8. No dedicated product research/extraction endpoint has been demonstrated in the audited main source; the workflow accepts product name/details and affiliate URL as input.

## Evidence labels

- VERIFIED — SOURCE RETRIEVED: exact current source fetched.
- VERIFIED — DEFINITION ISOLATION: exact body and indentation boundary checked.
- VERIFIED — ASSERTIONS MAPPED: test assertions inspected and tied to behavior.
- VERIFIED — CI RUN: a named GitHub Actions run succeeded.
- VERIFIED — LIVE BEHAVIOR: only when a safe approved runtime check proves it.
- UNVERIFIED: evidence is incomplete or indirect.

## Remaining work — task is not complete

1. Complete individual test-function and nested-helper records for the remaining test modules. So far, test-function records cover 8 of 17 modules; the remaining test files still need full per-definition treatment.
2. Audit every helper/class/method inside test modules separately where the task requires function-by-function coverage; do not count test fixtures as production logic.
3. Re-fetch and compare every existing production function/class record against current main. Correct stale source snapshots, line ranges, incomplete excerpts and broad parent records that swallow nested functions.
4. Finish detailed line-by-line explanations for every production definition, including defaults, validation, branches, loops, SQL, external calls, exceptions and return values.
5. Complete production call graph across OAuth ingest/refresh/revoke, content/image generation, publish/idempotency/reconciliation, analytics and diagnostics.
6. Finish test-to-production mapping, distinguishing mocks, SQL-shape harnesses, disposable PostgreSQL integration tests and CI execution.
7. Complete the eight migration reviews and five workflow reviews at statement/step level.
8. Deliver the final coverage matrix and prioritized findings after the above work is complete.

## Safety boundary

No publish-capable endpoint, OAuth mutation, provider-generation call, production database mutation, migration, deployment, merge or secret change is authorized by this audit. Any provider diagnostic with possible billing implications requires separate approval.
