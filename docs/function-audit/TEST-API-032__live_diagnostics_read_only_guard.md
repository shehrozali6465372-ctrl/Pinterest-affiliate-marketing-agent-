TEST-API-032 — `test_live_diagnostics_runs_read_only_pinterest_and_reports_side_effect_guard`

Source: `tests/test_api.py`, lines 732–795.

The test stubs database `SELECT 1`, credential retrieval, Pinterest account GET, image generation and content generation. It asserts each diagnostic stage succeeds, while the response explicitly reports no Pin, board or product persistence and no secrets returned. This is a mocked orchestration assertion; it does not prove live provider behavior or that generation is cost-free.