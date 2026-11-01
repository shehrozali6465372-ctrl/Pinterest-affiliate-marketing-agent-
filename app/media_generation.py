"""Generate Pin imagery with Workers AI and persist it in Cloudflare Images."""
from __future__ import annotations

import base64
import logging
import time
from urllib.parse import urlsplit

import httpx

from app.config import settings
from app.provider_retry import retry_delay_seconds

logger = logging.getLogger(__name__)

class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or returns unusable data."""

def _cloudflare_error_codes(response: httpx.Response) -> list[int | str]:
    codes: list[int | str] = []
    try:
        body = response.json()
        errors = body.get("errors", []) if isinstance(body, dict) else []
        if isinstance(errors, list):
            for item in errors[:3]:
                if isinstance(item, dict) and isinstance(item.get("code"), (int, str)):
                    codes.append(item["code"])
    except ValueError:
        pass
    return codes


def _safe_cloudflare_error(stage: str, response: httpx.Response) -> ImageGenerationError:
    codes = _cloudflare_error_codes(response)
    suffix = f"; provider_codes={codes}" if codes else ""
    logger.error("image_generation stage=cloudflare outcome=failed http_status=%s provider_codes=%s", response.status_code, codes)
    return ImageGenerationError(f"Cloudflare {stage} failed (HTTP {response.status_code}{suffix}).")


def generate_and_host_pin_image(*, product_name: str, product_details: str) -> dict[str, str]:
    """Generate an image, upload it to Cloudflare Images, and return its durable public URL."""
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
            if len(image_bytes) > 10 * 1024 * 1024:
                raise ImageGenerationError("Generated image exceeds Cloudflare Images' 10 MB single-upload limit.")

            # Persist the generated asset so Pinterest receives a stable public
            # URL and the product record can retain image provenance.
            uploaded = client.post(
                f"{base}/images/v1",
                headers=headers,
                files={"file": ("pinterest-pin.png", image_bytes, image_mime)},
                data={
                    "requireSignedURLs": "false",
                    "metadata": '{"source":"pinterest-model-1","generator":"workers-ai"}',
                },
            )
            if not uploaded.is_success:
                raise _safe_cloudflare_error("Images upload", uploaded)
            upload_body = uploaded.json()
            result = upload_body.get("result") if isinstance(upload_body, dict) else None
            image_id = result.get("id") if isinstance(result, dict) else None
            variants = result.get("variants") if isinstance(result, dict) else None
            image_url = variants[0] if isinstance(variants, list) and variants else None
            parts = urlsplit(image_url) if isinstance(image_url, str) else None
            if (
                not isinstance(upload_body, dict)
                or not isinstance(image_id, str) or not image_id
                or not isinstance(image_url, str)
                or parts is None or parts.scheme != "https" or not parts.netloc
                or upload_body.get("success") is not True
            ):
                raise ImageGenerationError("Cloudflare Images upload returned no verified public image URL or image ID.")
            return {
                "image_url": image_url,
                "model": settings.cloudflare_image_model,
                "cloudflare_image_id": image_id,
                "mime_type": image_mime,
                "byte_length": str(len(image_bytes)),
            }
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
