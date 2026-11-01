# test_learning_loop_parses_documented_pinterest_summary_metrics

- **Unique ID:** TEST-LEARNING-002
- **Definition type:** test function
- **Source:** `tests/test_learning.py:24-74`
- **Production target:** `app.learning.run_learning_loop`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Provides one fake succeeded publication and a mocked analytics response with per-metric summary wrappers. Asserts requested metrics, persisted snapshot, aggregate impression/save/outbound totals, 5% outbound-click rate and model_trained=false.

## Evidence boundary
All database connections and Pinterest HTTP responses in this test module are mocked. These assertions do not establish live analytics API contract correctness, token refresh behavior, Neon persistence or production analytics completeness.
