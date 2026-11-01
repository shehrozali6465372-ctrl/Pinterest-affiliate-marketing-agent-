# _safe_cloudflare_error

- **Unique ID:** `FN-APP-MEDIA-GENERATION-PY-003`
- **Source:** `app/media_generation.py:34-40`
- **Source blob SHA:** `e4a62e8ca628ee906bc59915810edc20e3c8f8e7`
- **Snapshot:** `main source snapshot 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Creates a safe Cloudflare error summary. Verify token/authorization and uploaded image data cannot leak through logs or API error details.

## Exact isolated source

```python
def _safe_cloudflare_error(stage: str, response: httpx.Response) -> ImageGenerationError:
    codes = _cloudflare_error_codes(response)
    suffix = f"; provider_codes={codes}" if codes else ""
    logger.error("image_generation stage=cloudflare outcome=failed http_status=%s provider_codes=%s", response.status_code, codes)
    return ImageGenerationError(f"Cloudflare {stage} failed (HTTP {response.status_code}{suffix}).")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION RANGE`: single definition isolated.
- `UNVERIFIED — LOGIC CORRECTNESS`: tests and call graph still require verification.
- `UNVERIFIED — LIVE BEHAVIOR`: no external provider call was executed.

## Required checks

Review all call sites, test cases, input boundaries, exception behavior, provider contracts, retry safety and secret redaction.
