# generate_and_host_pin_image — source-level review

- ID: `FN-APP-MEDIA-GENERATION-PY-004`; source `app/media_generation.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime/provider verification: NOT RUN; provider use may be billable.

## Control flow
1. Requires Cloudflare API token and account ID.
2. Builds vertical 2:3 product-lifestyle prompt using product name and first 2500 chars of supplied details.
3. POSTs configured Workers AI model endpoint with 90s total/10s connect timeout.
4. Retries at most once for 500/502/503/504 or HTTP 429 containing code 3040, using bounded retry_delay_seconds; otherwise raises sanitized ImageGenerationError.
5. Accepts raw image/* response or JSON result.image Base64; validates PNG/JPEG/WebP MIME and minimum 1024 bytes.
6. Base64 encodes bytes and returns a data URL plus model ID.

## Important distinction and risks
Despite function name, it does not upload to Cloudflare Images or persist a hosted asset. Returned data URL is later converted to Pinterest image_base64. Retry can incur another provider charge. Fake tests do not prove live model availability/permissions. No generation call was made.
