# strip_required_text — source-level review

- ID: `FN-APP-MAIN-PY-005`; source `app/main.py:71-77`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic field validator strips leading/trailing whitespace from product_name/product_details and raises ValueError if result is empty. Returns normalized string. It does not normalize internal whitespace or validate factual claims.

## Callers and tests
Attached to ProductInput name/details fields; validation errors are returned by FastAPI as 422. API tests cover whitespace-only product name.
