# test_persistence_constraint_failure_logs_safe_schema_diagnostics

- **Unique ID:** TEST-WORKFLOW-PERSIST-003
- **Definition type:** test function
- **Source:** `tests/test_workflow_persistence_recovery.py:116-157`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Simulates a database not-null constraint failure and checks safe schema diagnostic logging rather than exposing sensitive values.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
