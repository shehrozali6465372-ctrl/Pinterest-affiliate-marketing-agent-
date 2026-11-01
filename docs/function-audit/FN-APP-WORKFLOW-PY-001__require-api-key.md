# _require_api_key — source-level review

- ID: `FN-APP-WORKFLOW-PY-001`; source `app/workflow.py:25-27`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Requires APP_API_KEY to be configured, X-API-Key header present and constant-time equal; any missing config/header or mismatch raises HTTP 401. Unlike main.require_api_key, this workflow dependency fails closed. It is attached at router endpoint dependency level to /workflow/publish-product.

## Risk and tests
The route is a real provider-generation and Pinterest publishing workflow, so fail-closed behavior is required. Workflow tests set configured key and verify missing/wrong key rejection. No endpoint was invoked.
