# GeneratedContent — source-level review

- ID: `FN-APP-CONTENT-GENERATION-PY-001`; source `app/content_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic model defining four required non-empty string fields: pin_idea (max 500), title (max 100), description (max 2000), alt_text (max 500). Pydantic rejects missing fields, empty strings and over-limit values during model validation. It does not independently verify factual truth, Pinterest policy, disclosure presence or image correspondence; those are handled by generator prompt/post-validation logic.

## Callers and tests
Constructed by `generate_pin_content` via `GeneratedContent.model_validate(parsed_content)`. Tests in `test_deepseek_completion.py` exercise valid/invalid JSON and schema cases using fake HTTP responses. No live model output was used.
