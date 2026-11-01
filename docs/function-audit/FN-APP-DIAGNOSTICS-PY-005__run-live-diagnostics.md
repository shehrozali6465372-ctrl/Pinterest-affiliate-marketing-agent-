# run_live_diagnostics — source-level review

- ID: `FN-APP-DIAGNOSTICS-PY-005`; source `app/diagnostics.py:144-242`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/provider verification: NOT RUN.

## Control flow and side effects
1. Router dependency requires configured APP_API_KEY; missing or mismatched key returns 401.
2. Runs DB `SELECT 1`; catches exceptions into a sanitized database failure result.
3. Loads stored Pinterest credential and GETs /user_account; missing credential and other failures are recorded without exposing token.
4. Only when both DB and Pinterest checks pass does it call Cloudflare Workers AI image generation. It converts returned data URL to Pinterest media source and reports that image was not uploaded to Cloudflare Images or persisted.
5. If media exists and LLM key is configured, calls DeepSeek multimodal generation and validates non-empty title/description/alt text. Otherwise marks the check failed.
6. Returns aggregate ok/checks and side-effect flags; it does not create a board/Pin/product or write image storage.

## Cost and test evidence
Although no Pin or product is created, generation calls may incur Cloudflare and DeepSeek usage. `tests/test_deepseek_failure_diagnostics.py` and related diagnostics tests stub DB, Pinterest and provider functions; they do not establish live provider access. The manual safe-production-diagnostics workflow invokes this endpoint and is not a free/read-only probe.

Do not call this endpoint during a no-cost audit. It was not invoked.
