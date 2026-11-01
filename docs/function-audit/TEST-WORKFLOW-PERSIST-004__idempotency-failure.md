# test_idempotency_state_failure_logs_safe_stage-and-correlation-id

- **Unique ID:** TEST-WORKFLOW-PERSIST-004
- **Definition type:** test function
- **Source:** `tests/test_workflow_persistence_recovery.py:159-179`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Forces idempotency-state lookup failure and checks safe stage/correlation metadata is logged.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
