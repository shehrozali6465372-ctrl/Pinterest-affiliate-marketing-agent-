# generate_and_host_pin_image

- **Unique ID:** `FN-APP-MEDIA-GENERATION-PY-004`
- **Source:** `app/media_generation.py:41-109`
- **Source blob SHA:** `e4a62e8ca628ee906bc59915810edc20e3c8f8e7`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Builds the image-generation request for Cloudflare Workers AI, authenticates with configured Cloudflare credentials, requests an image, then uploads/hosts it through the configured Cloudflare Images account and returns an image URL/model metadata. Verify request model/schema, binary conversion, upload endpoint, MIME/size constraints, error redaction and whether returned URL is publicly fetchable by Pinterest.

## Exact isolated source

```python
def generate_and_host_pin_image(*, product_name: str, product_details: str) -> dict[str, str]:
    """Generate an image and return a data URL; no separate image host is used."""
    if not settings.cloudflare_api_token or not settings.cloudflare_account_id:
        raise ImageGenerationError("Cloudflare Workers AI and account credentials are not configured.")
    prompt = (
        "Create a polished, realistic vertical 2:3 Pinterest product lifestyle image for a USA "
        "home organization audience. Feature the product accurately, with no logos, watermarks, "
        "fabricated text, extra product features, or misleading claims. Use a clean, bright, "
        "editorial kitchen setting, balanced composition, and clear product visibility. Do not add typography. Product: "
        f"{product_name}. Verified details: {product_details[:2500]}"
    )
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}
    timeout = httpx.Timeout(90.0, connect=10.0)
    base = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}"
    try:
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(2):
                generated = client.post(
                    f"{base}/ai/run/{settings.cloudflare_image_model}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"prompt": prompt},
                )
                if not generated.is_error:
                    break
                codes = _cloudflare_error_codes(generated)
                retryable = (
                    generated.status_code in {500, 502, 503, 504}
                    or (generated.status_code == 429 and 3040 in codes)
                )
                delay = retry_delay_seconds(generated, attempt + 1) if retryable and attempt == 0 else None
                if delay is None:
                    raise _safe_cloudflare_error("Workers AI generation", generated)
                logger.warning(
                    "image_generation stage=cloudflare outcome=retrying http_status=%s provider_codes=%s retry_delay_ms=%s attempt=%s",
                    generated.status_code, codes, int(delay * 1000), attempt + 1,
                )
                time.sleep(delay)
            else:
                raise ImageGenerationError("Cloudflare Workers AI generation retry budget exhausted.")
            content_type = generated.headers.get("content-type", "").lower()
            if "image/" in content_type:
                image_bytes = generated.content
                image_mime = content_type.split(";", 1)[0]
            else:
                body = generated.json()
                result = body.get("result") if isinstance(body, dict) else None
                image_value = result.get("image") if isinstance(result, dict) else None
                if not isinstance(image_value, str) or not image_value:
                    raise ImageGenerationError("Cloudflare Workers AI returned no image data (HTTP 200).")
                image_bytes = base64.b64decode(image_value, validate=True)
                image_mime = "image/png"
            if image_mime not in {"image/png", "image/jpeg", "image/webp"}:
                raise ImageGenerationError("Cloudflare Workers AI returned an unsupported image content type.")
            if len(image_bytes) < 1024:
                raise ImageGenerationError("Cloudflare Workers AI returned an unexpectedly small image.")
            encoded = base64.b64encode(image_bytes).decode("ascii")
            return {"image_url": f"data:{image_mime};base64,{encoded}", "model": settings.cloudflare_image_model}
    except ImageGenerationError:
        raise
    except httpx.TimeoutException as exc:
        logger.error("image_generation stage=cloudflare outcome=failed exception_type=%s", type(exc).__name__)
        raise ImageGenerationError("Cloudflare image generation timed out; check provider latency and retry budget.") from exc
    except httpx.HTTPError as exc:
        logger.error("image_generation stage=cloudflare outcome=failed exception_type=%s", type(exc).__name__)
        raise ImageGenerationError(f"Cloudflare image generation request failed ({type(exc).__name__}).") from exc
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("image_generation stage=cloudflare_response outcome=failed exception_type=%s", type(exc).__name__)
        raise ImageGenerationError(f"Cloudflare returned an invalid image response ({type(exc).__name__}).") from exc
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from the exact source blob above.
- `VERIFIED — DEFINITION ISOLATION`: one definition and its complete body only.
- `UNVERIFIED — LOGIC CORRECTNESS`: call graph, tests and edge cases remain to be proven.
- `UNVERIFIED — LIVE PINTEREST BEHAVIOR`: no provider call was executed.

## Remaining checks

Trace every caller, review tests, compare request/response with Pinterest API contract, inspect all exceptions and timeout cases, and verify no duplicate Pin can result from retries. Do not call this function during this audit.
