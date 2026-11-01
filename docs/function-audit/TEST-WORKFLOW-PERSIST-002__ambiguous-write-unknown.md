# test_ambiguous_pin_publish_marks_attempt_unknown_and_blocks_safe_retry

- **Unique ID:** TEST-WORKFLOW-PERSIST-002
- **Definition type:** test function
- **Source:** `tests/test_workflow_persistence_recovery.py:76-114`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Simulates an ambiguous Pinterest write and asserts the publication is marked unknown and a subsequent safe retry is blocked.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
