# nonblank — source-level review

- ID: `FN-APP-WORKFLOW-PY-004`; source `app/workflow.py:54-59`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic field validator receives product_name, product_details or board_name; if value.strip() is empty it raises ValueError; otherwise returns stripped value. It normalizes surrounding whitespace rather than preserving it. It does not validate semantic content or factual accuracy.

## Callers and tests
Attached to ProductWorkflowInput fields. FastAPI/Pydantic converts validation failures into 422. Workflow tests exercise blank and bounded request values.
