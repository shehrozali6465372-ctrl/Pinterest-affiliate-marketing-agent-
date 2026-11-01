# ImageGenerationError — source-level review

- ID: `FN-APP-MEDIA-GENERATION-PY-001`; source `app/media_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/provider verification: NOT RUN.

## Behavior
Dedicated RuntimeError subclass for missing Cloudflare configuration, provider rejection, malformed image response, unsupported MIME, too-small image and transport/timeout failures. No custom fields or methods; message and chained exception are created at raise sites. Workflow and diagnostics routes catch it and map it to sanitized HTTP outcomes.

## Tests
Provider retry/media tests inject fake HTTP responses and errors. They do not establish Cloudflare account permissions, current model availability or actual generation success. No provider call was made.
