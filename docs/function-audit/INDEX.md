# Function audit index — Model 1

Repository: `shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-`
Branch: `main`
Audit refresh: 2026-11-01
Application source baseline: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
Audit-document HEAD at refresh: `6e22a88e110fa5109c1b939e1e5285cec524f7e7`
Mode: READ-ONLY source review and documentation. No application code, production DB, credentials, provider state, deployment or Pinterest Pins changed.

## Current repository inventory

- Python files under app/, scripts/ and tests/: 30.
- Test modules: 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Audit Markdown files including this index: 221.
- Separate audit/review records excluding index: 220.
- Individual test_api.py records: 40/40.
- Duplicate audit record IDs: 0.

The audit-document count is not a completion percentage. Several records cover grouped test helpers and migration/workflow files; production definitions still require a full exact-source reconciliation and complete per-definition explanation.

## Work completed in this continuation

- Re-enumerated all Python definition declarations across app/, scripts/ and tests/ against application baseline commit.
- Added individual audit records for the final nine API test functions: TEST-API-032 through TEST-API-040. tests/test_api.py now has records for all 40 test functions.
- Added grouped, source-grounded helper audits for database-pool unit and opt-in integration tests, DeepSeek completion/diagnostic test helpers, and Pinterest diagnostic test helpers.
- Added statement-level static review of all eight SQL migrations in MIGRATIONS-001-008.md.
- Added step-level static review of all five GitHub Actions workflows in WORKFLOWS-001-005.md.
- No tests or workflows were executed as part of this read-only continuation.

## Key source findings

1. `app/learning.py::run_learning_loop` filters confirmed successful Pins by account, requests analytics, validates and persists snapshots, and explicitly returns `model_trained: false`. This is analytics ingestion/descriptive evaluation, not predictive ML training.
2. The Learning Loop obtains a stored access token for analytics GET calls. The function itself does not invoke token refresh. Automatic refresh on expiry is not demonstrated by this route; inspect the broader call path before classifying it as a defect.
3. The daily Learning Loop workflow calls the protected endpoint and writes analytics snapshots to production storage. It is not evidence that model training occurs.
4. The read-only production verification workflow uses GET requests. The safe-production-diagnostics workflow POST invokes Cloudflare image generation and DeepSeek content generation; it can consume provider credits despite not publishing a Pin.
5. CI definitions differ: ci.yml uses Python 3.11 and PostgreSQL 16 service with TEST_DATABASE_URL; tests.yml uses Python 3.12 and does not configure a test database. A green run must be attributed to its exact workflow and commit.
6. Migration 003 enforces successful publication rows have a Pin ID and uniqueness by content_version_id + board_id. Migration 007 adds nullable account_id, leaving legacy rows unassigned. Migration 006 stores analytics snapshots unique by Pin and period.
7. The Pinterest write helper attaches the affiliate URL in the Pin `link` field. This is not evidence of native Pinterest Product Tag support.
8. No dedicated product research/extraction endpoint has been demonstrated in the audited main source; the end-to-end workflow accepts product name/details and affiliate URL as input.
9. The disposable PostgreSQL pool integration test is explicitly opt-in and terminates a backend session. It must only target the exact guarded disposable Neon test branch; it was not run in this audit.
10. Fake HTTP clients, fake cursors and stateful in-memory harnesses validate application branches but do not prove live Pinterest, DeepSeek, Cloudflare or PostgreSQL behavior.

## Evidence labels

- VERIFIED — SOURCE RETRIEVED: exact source fetched from the recorded application baseline.
- VERIFIED — DEFINITION ISOLATION: exact body and indentation boundary checked.
- VERIFIED — ASSERTIONS MAPPED: test assertions inspected and tied to behavior.
- VERIFIED — CI RUN: a named GitHub Actions run succeeded for a named commit.
- VERIFIED — LIVE BEHAVIOR: only when a safe approved runtime check proves it.
- UNVERIFIED: evidence is incomplete or indirect.

## Remaining work — task is not complete

1. Complete individual function/class/method coverage for all remaining test modules. Current continuation has complete individual test-function records for test_api.py, but other test modules still need a full test-function and nested-helper coverage matrix.
2. Audit every test fixture, fake class, nested method and helper separately where function-by-function scope requires it. Grouped helper records exist for some modules but do not yet provide a complete per-definition inventory for all 17 modules.
3. Re-fetch every existing production definition record and compare it against the exact source blob SHA, current line ranges, body boundaries and nested definitions. Correct broad parent records that swallow nested functions.
4. Finish detailed line-by-line explanations for every production definition in app/, scripts/ and relevant config/model classes, including defaults, validation, branches, loops, SQL, provider calls, exception mapping and return values.
5. Complete the end-to-end call graph across OAuth ingest/refresh/revoke, credential encryption, content/image generation, publish/idempotency/recovery/reconciliation, analytics/Learning Loop and diagnostics.
6. Finish the test-to-production mapping and classify every assertion as mock/unit, SQL-shape harness, disposable PostgreSQL integration or executed CI evidence.
7. Cross-check workflow claims against the actual route implementation and current GitHub Actions run history. Static YAML review alone does not prove enabled schedules, configured secrets or successful runtime behavior.
8. Deliver the final per-file/per-definition coverage matrix and prioritized risk register only after the above work is complete.

## Safety boundary

No publish-capable endpoint, OAuth mutation, provider-generation call, production database mutation, migration, deployment, merge or secret change is authorized by this audit. Any provider diagnostic with possible billing implications requires separate approval. The audit must not publish real Pins.
