# Test review — publication, Learning Loop and token refresh

- Unique ID: TEST-REVIEW-001
- Source files: tests/test_publish_recovery_state_machine.py, tests/test_publish_reconciliation.py, tests/test_learning.py, tests/test_token_refresh.py, tests/test_workflow_persistence_recovery.py
- Status: PARTIALLY VERIFIED — STATIC ASSERTIONS INSPECTED; TEST EXECUTION NOT PERFORMED

## Publication recovery state machine

The state-machine test harness stubs the database connection and simulates SQL-shaped state. Assertions cover unknown, pending and succeeded states blocking retries without INSERT/UPDATE, and failed state reserving a retry. This verifies intended branching against the fake harness, not PostgreSQL row-lock behavior or true concurrent transactions.

## Publication reconciliation

The inspected tests assert authentication is required, status reads only the DB, successful reconciliation requires a Pin ID, failed reconciliation cannot include a Pin ID, only unknown states can be reconciled, and a successful/failed reconciliation changes retry eligibility. The stateful harness checks audit metadata and rejects a second transition. These are test assertions, not proof that Pinterest evidence is independently trustworthy.

## Learning Loop

The inspected tests assert account-scoped publication selection, documented analytics metric parsing, persistence of valid snapshots, rejection of incomplete metric payloads, omitted metrics treated as zero where the fixture expects it, outbound click-rate calculation, and model_trained false. The tests explicitly demonstrate metrics collection/persistence; they do not demonstrate predictive model training.

## Token refresh

The inspected tests assert service-key authentication, token rotation persistence, no secret values returned in the response, preservation of the prior refresh token if the provider omits rotation, rejection of expired/malformed refresh-token expiry before provider call, and encrypted persistence in a disposable PostgreSQL integration test. The disposable DB test is skipped unless TEST_DATABASE_URL is set. No test was executed in this audit.

## Workflow persistence and recovery

The inspected tests assert persistence failure prevents Pinterest POST /pins, ambiguous publish outcomes become unknown and block safe retry, and several failure paths are classified before any Pinterest write. These tests use monkeypatches and fake provider responses; they do not establish live Pinterest behavior.

## Verification tags

- VERIFIED — TEST SOURCE PRESENT: test source files retrieved from GitHub.
- VERIFIED — ASSERTION MAPPING: assertions listed above are present in retrieved test source.
- UNVERIFIED — TEST EXECUTION: CI results were not fetched or run in this continuation.
- UNVERIFIED — REAL POSTGRES CONCURRENCY: fake harness does not prove DB row-lock behavior.
- UNVERIFIED — LIVE PROVIDER BEHAVIOR: Pinterest and OAuth provider calls were not performed.

## Gaps to investigate

1. Fetch latest CI workflow run and confirm which test jobs actually executed; do not assume green from old reports.
2. Inspect real PostgreSQL integration test setup and ensure TEST_DATABASE_URL is isolated/disposable, not production.
3. Check transaction boundaries and SELECT ... FOR UPDATE behavior against actual schema/indexes.
4. Map each production function to its tests and identify untested branches, including network timeout after Pinterest accepted a Pin.
5. Inspect analytics migration and query semantics to ensure metric windows, account isolation and deduplication are correct.

No production DB, OAuth credentials, Pinterest account or publishing endpoint was touched.
