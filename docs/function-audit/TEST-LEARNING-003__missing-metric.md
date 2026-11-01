# test_missing_requested_metric_is_not_persisted

- **Unique ID:** TEST-LEARNING-003
- **Definition type:** test function
- **Source:** `tests/test_learning.py:77-113`
- **Production target:** `app.learning.run_learning_loop`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Provides only an impression metric and asserts analytics payload failure, no snapshot persistence, no token leakage in response, and zero writes. This covers the incomplete per-metric-wrapper response branch.

## Evidence boundary
All database connections and Pinterest HTTP responses in this test module are mocked. These assertions do not establish live analytics API contract correctness, token refresh behavior, Neon persistence or production analytics completeness.
