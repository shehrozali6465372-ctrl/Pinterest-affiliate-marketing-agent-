# ContentGenerationError — source-level review

- ID: `FN-APP-CONTENT-GENERATION-PY-002`; source `app/content_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Dedicated RuntimeError subclass marking content-generation failures. It carries no custom fields or behavior; message and chained original exception are supplied at raise sites. API routes catch it and convert to HTTP 503. It distinguishes expected provider/content failure from unrelated programming/DB exceptions.

## Callers and tests
Raised by `generate_pin_content` for missing API key, HTTP/transport failure, malformed response envelope, unsupported content, invalid JSON, truncation and schema failure. API and DeepSeek tests assert selected message/status categories with fake clients. No provider request was made.
