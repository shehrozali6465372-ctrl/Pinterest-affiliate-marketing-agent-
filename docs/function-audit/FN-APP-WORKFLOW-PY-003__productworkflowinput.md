# ProductWorkflowInput — source-level review

- ID: `FN-APP-WORKFLOW-PY-003`; source `app/workflow.py:43-51`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema requires product_name 1–300, product_details 1–10000, affiliate_url 8–4096 and account_id 1–200. board_name defaults to Modern Living Hub kitchen/home board and is 1–100; board_description has default and max 500. Validators strip/reject blank name/details/board name and validate destination URL as absolute HTTP(S), host present, no userinfo and no surrounding whitespace. Affiliate URL string is returned unchanged.

## Limitation
Product name/details/account are caller supplied; schema does not fetch product facts, verify affiliate ownership, validate product claims or check account exists. Used by publish_product_end_to_end, which can generate content and publish a real Pin.
