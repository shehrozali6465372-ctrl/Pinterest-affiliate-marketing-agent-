# test_publication_attempt_create_failure_is_classified_before_pinterest_write

- **Unique ID:** TEST-WORKFLOW-PERSIST-005
- **Definition type:** test function
- **Source:** `tests/test_workflow_persistence_recovery.py:181-217`
- **Production target:** `app.database.begin_publish_attempt`, `app.database.finish_publish_attempt`, `app.workflow.publish_product_end_to_end`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Forces publication-attempt creation to fail and asserts the Pinterest write helper is not called; failure is classified before external side effect.

## Evidence boundary
These tests use fake database/cursor/provider harnesses and monkeypatching. They establish asserted control-flow behavior in the test harness, not PostgreSQL locking/concurrency guarantees or actual Pinterest side-effect outcomes.
