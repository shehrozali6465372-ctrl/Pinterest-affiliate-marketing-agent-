# test_learning_loop_parses_top_level_summary_metrics_and_omitted_zero_metrics

- **Unique ID:** TEST-LEARNING-004
- **Definition type:** test function
- **Source:** `tests/test_learning.py:116-157`
- **Production target:** `app.learning.run_learning_loop`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Supplies response body under all.summary_metrics with outbound click omitted. Asserts snapshot is saved and omitted metric becomes zero, consistent with the implementation's documented interpretation.

## Evidence boundary
All database connections and Pinterest HTTP responses in this test module are mocked. These assertions do not establish live analytics API contract correctness, token refresh behavior, Neon persistence or production analytics completeness.
