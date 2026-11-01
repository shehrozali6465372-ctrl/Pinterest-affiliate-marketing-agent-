# pinterest_read_only_diagnostic — source-level review

- ID: `FN-APP-DIAGNOSTICS-PY-003`; source `app/diagnostics.py:48-136`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Control flow
Requires caller-supplied account_id query parameter and fail-closed router API key. Initializes explicit side-effect flags false. Loads encrypted credential; maps missing credential to structured not-connected result, invalid AES tag/key config/DB config/psycopg error to sanitized HTTP 503. GETs Pinterest /user_account with Bearer token and bounded timeout. Transport failure returns sanitized 503; upstream 401/403 maps 401 and other failures 502. Success returns account_id/check/status only, not token. No board/Pin write or AI generation.

## Tests and limits
`tests/test_diagnostics.py` stubs vault and HTTP clients to assert caller account selection, no generation and secret redaction. It is a real external GET if invoked; no live request was made.
