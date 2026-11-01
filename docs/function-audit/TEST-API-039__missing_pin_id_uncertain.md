TEST-API-039 — `test_end_to_end_missing_pin_id_is_marked_uncertain`

Source: `tests/test_api.py`, lines 1032–1094.

The fake Pinterest write returns HTTP 201 without a Pin ID. The route responds HTTP 502 with an uncertain-outcome message and records the attempt as `unknown` with `missing_pin_id`. The test checks conservative recovery semantics in a mocked workflow; no real Pin is created.