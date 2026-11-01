# test_failed_publication_can_reserve_one_retry

- **Unique ID:** TEST-PUBLISH-STATE-004
- **Definition type:** test function
- **Source:** `tests/test_publish_recovery_state_machine.py:69-74`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Asserts a failed publication state can reserve a subsequent attempt under the fake cursor state model.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
