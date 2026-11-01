# generate_pin_content — source-level review

- ID: `FN-APP-CONTENT-GENERATION-PY-005`; source `app/content_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/provider verification: NOT RUN; generation may be billable.

## Control flow
1. Fails with ContentGenerationError if LLM key missing.
2. Builds DeepSeek chat-completions endpoint and constrained prompt: product claims only from supplied facts, alt text from visible image, required affiliate disclosure, exact JSON keys/lengths.
3. Sends text + image_url multimodal user content, JSON-object response format, disabled thinking, temperature 0.4, max_tokens 2400, non-streaming, 60s/10s timeout.
4. HTTP 500/503 and timeout/network errors get at most one bounded retry via retry_delay_seconds; other HTTP/transport errors become sanitized ContentGenerationError.
5. Invalid response envelope, missing/non-text content, invalid model JSON and schema validation each get one corrective retry; a second failure is classified and raised. Token-limit truncation receives a specific error.
6. Validates GeneratedContent, appends mandatory affiliate disclosure if missing, truncates description while preserving disclosure, returns content and configured model ID.

## Tests, costs and risks
`test_deepseek_completion.py`, `test_deepseek_http_diagnostics.py` and `test_provider_retry.py` use fake responses. Retries can double provider calls/cost. The prompt says use only supplied facts, but model output still requires factual review. No live provider request was made.
