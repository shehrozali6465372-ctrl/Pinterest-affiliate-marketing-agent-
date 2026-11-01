# _safe_cloudflare_error — source-level review

- ID: `FN-APP-MEDIA-GENERATION-PY-003`; source `app/media_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Calls _cloudflare_error_codes, formats a bounded suffix containing parsed codes when present, logs stage/status/codes, and returns ImageGenerationError containing stage and HTTP status. It does not log raw response body or request headers. The returned exception is raised by caller.

## Callers and tests
Used when Workers AI response is error and no retry delay is authorized. Tests inject provider errors. Provider codes are trusted only as diagnostic strings/numbers; do not treat them as a stable contract without current Cloudflare docs.
