# Production definition review — content, image and Pinterest clients

Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0.

## app/content_generation.py — blob SHA 12d8685abb2883bf4e47526aa99acffc5fd7c36c
- GeneratedContent: Pydantic schema for pin_idea/title/description/alt_text with field constraints (inspect model declarations in source).
- ContentGenerationError: dedicated runtime failure type for provider/content failures.
- _safe_http_failure_metadata(response, elapsed_ms): extracts bounded/sanitized status, provider code, content type, byte count, duration and request ID; avoids logging response body or secret values.
- nested sanitize(value, limit): strips/normalizes unsafe metadata and redacts sensitive values before logging.
- generate_pin_content(...): validates LLM key, builds multimodal DeepSeek chat-completions payload with product text and image data URL, requests JSON object output, disables thinking, uses bounded timeout, retries selected 500/503 and transport failures once, retries malformed envelope/model JSON/schema once with corrective hint, validates model response, enforces affiliate disclosure and description limit, returns GeneratedContent and model ID. External provider calls may incur cost. No provider calls were made in audit.

## app/media_generation.py — blob SHA e4a62e8ca628ee906bc59915810edc20e3c8f8e7
- ImageGenerationError: explicit error type for invalid/unavailable image generation.
- _cloudflare_error_codes(response): parses at most first three integer/string provider error codes; malformed body returns empty list.
- _safe_cloudflare_error(stage, response): logs sanitized status/provider codes and constructs a bounded error message.
- generate_and_host_pin_image(product_name, product_details): requires Cloudflare token/account ID; builds product-accurate vertical image prompt; POSTs Workers AI model with bounded retry for selected 5xx and capacity code 3040; accepts image/* body or JSON base64 result; validates supported MIME and >=1024 bytes; returns data URL and model ID. It does not upload to Cloudflare Images or persist image asset. Provider use may be billable.

## app/pinterest.py — blob SHA 6ccc51b2cf8a289f6989e872179a0014cfe6f372
- PinterestPublishError: carries outcome_uncertain, HTTP status and error code.
- PinterestPublishError.__init__: initializes RuntimeError and stores certainty/status/error metadata.
- image_media_source(image_url): accepts supported image data URL formats, strict Base64-decodes and rejects malformed/small payload; returns Pinterest image_base64 source; legacy non-data URLs return image_url source.
- publish_image_pin(...): requires configured token and board; builds POST /pins payload including affiliate URL in link; sends request with timeout; transport errors and 5xx are uncertain; 4xx rejected; non-JSON or missing Pin ID treated uncertain; success returns provider ID/metadata. Real Pinterest write; not invoked.
- PinterestReadError: read-only API failure type.
- list_board_pins_read_only(...): GETs board Pin pages, follows bookmarks, detects repeated bookmark and page cap, returns items plus pagination completeness; no writes.
- get_pin_read_only(...): GETs Pin detail and returns JSON; no writes.

## Important boundaries
- A normal affiliate destination in Pin link field is not native Pinterest Product Tag.
- Base64 media avoids requiring a public image host; the generated data URL is sent to Pinterest directly.
- Cloudflare Workers AI generation and Cloudflare Images storage are different services. The inspected implementation calls Workers AI and does not call the Images upload API.
- Static source review is not proof of current provider API acceptance, permissions, quota, cost or live behavior.