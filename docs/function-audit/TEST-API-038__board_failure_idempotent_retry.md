TEST-API-038 — `test_end_to_end_board_failure_allows_same_idempotency_key_retry`

Source: `tests/test_api.py`, lines 950–1031.

A mocked Pinterest board lookup fails on the first request before content/image generation or persistence. The same idempotency key is retried; the second board lookup succeeds and the fake Pin write returns an ID. Assertions verify the retry publishes once in the harness, preserves the affiliate URL and invokes generation/persistence only on the successful attempt. All external calls and persistence are stubbed; this is not a real publication test.