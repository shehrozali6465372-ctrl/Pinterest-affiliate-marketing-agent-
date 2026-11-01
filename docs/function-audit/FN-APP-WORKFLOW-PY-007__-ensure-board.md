# _ensure_board — source-level review

- ID: `FN-APP-WORKFLOW-PY-007`; source `app/workflow.py:84-99`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Behavior
GETs `/boards?page_size=100`; reads response.items only; finds first dict with case-insensitive exact name match and non-empty id; returns that ID. If no match, POSTs /boards with name/description; requires non-empty string id or raises HTTP 502. It does not follow Pinterest pagination bookmarks.

## Callers, tests and risks
Called before image/content generation and before product persistence in publish_product_end_to_end. Board creation is a real side effect; if later provider or DB step fails, the board remains. Existing matching board beyond first 100 can be missed, causing duplicate board creation. Workflow tests mock this helper; no live board read/write occurred.
