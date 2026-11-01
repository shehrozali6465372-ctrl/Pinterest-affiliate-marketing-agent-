# test_succeeded_publication_blocks_duplicate_retry

- **Unique ID:** TEST-PUBLISH-STATE-003
- **Definition type:** test function
- **Source:** `tests/test_publish_recovery_state_machine.py:62-67`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts an already succeeded publication cannot reserve another publish attempt.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
