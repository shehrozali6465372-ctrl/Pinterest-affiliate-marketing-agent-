# test_unknown_publication_blocks_retry_without_state_mutation

- **Unique ID:** TEST-PUBLISH-STATE-001
- **Definition type:** test function
- **Source:** `tests/test_publish_recovery_state_machine.py:48-53`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Runs begin_publish_attempt through a fake cursor state harness with publication status unknown. Asserts the attempt is blocked and the state is not mutated.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
