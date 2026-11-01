# test_persistence_failure_never_attempts_pin_publish

- **Unique ID:** TEST-WORKFLOW-PERSIST-001
- **Definition type:** test function
- **Source:** `tests/test_workflow_persistence_recovery.py:45-74`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Forces persistence to fail and asserts the mocked Pinterest request is not called, preserving the ordering requirement that durable publication state exists before external write.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
