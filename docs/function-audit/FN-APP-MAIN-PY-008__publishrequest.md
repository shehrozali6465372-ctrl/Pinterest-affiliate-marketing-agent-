# PublishRequest — source-level review

- ID: `FN-APP-MAIN-PY-008`; source `app/main.py:104-107`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema requires positive product_id and content_version_id. It does not verify that the content version belongs to the product; route/database lookup enforces that relationship.

## Callers and tests
Used by compatibility `POST /publish` wrapper, which delegates to publish_product_content and can create a real Pin. Tests cover invalid/missing publish IDs and wrapper behavior. No publish was invoked.
