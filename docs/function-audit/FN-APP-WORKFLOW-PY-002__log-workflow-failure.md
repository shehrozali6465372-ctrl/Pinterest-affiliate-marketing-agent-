# _log_workflow_failure — source-level review

- ID: `FN-APP-WORKFLOW-PY-002`; source `app/workflow.py:29-40`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Reads structured exception diagnostic fields only: exception type, SQLSTATE, table, column and constraint identifiers, plus stage/request ID/optional HTTP status. Missing fields become "unknown". Emits one structured error log; deliberately excludes exception message, request body, SQL, product data, provider response and tokens.

## Callers and tests
Called on idempotency read, Pinterest credential verification, board resolution, image/content generation, persistence, attempt creation and Pin publish/recording failures. Ensure caller-supplied request ID has already been sanitized; this helper itself does not sanitize it. Tests inspect sanitized logging behavior with fake exceptions.
