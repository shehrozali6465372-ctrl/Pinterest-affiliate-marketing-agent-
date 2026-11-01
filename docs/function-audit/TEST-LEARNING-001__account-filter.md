# test_learning_loop_filters_published_pins_by_account

- **Unique ID:** TEST-LEARNING-001
- **Definition type:** test function
- **Source:** `tests/test_learning.py:5-21`
- **Production target:** `app.learning.run_learning_loop`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Mocks credential lookup and database connection. Asserts the SQL filters successful publications and account_id matches the caller, then checks empty-account response has zero Pins, model_trained=false and waiting_for_published_pins.

## Evidence boundary
All database connections and Pinterest HTTP responses in this test module are mocked. These assertions do not establish live analytics API contract correctness, token refresh behavior, Neon persistence or production analytics completeness.
