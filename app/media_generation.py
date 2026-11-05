"""Cloudflare Workers AI image generation with bounded response memory."""
from __future__ import annotations

import base64
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
_ERROR_BODY_LIMIT = 64 * 1024


class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or returns unusable data."""


def _read_limited_response(response: httpx.Response, max_bytes: int) -> bytes:
    """Read a streamed response without ever buffering more than max_bytes."""
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise ImageGenerationError("Cloudflare Workers AI image response exceeds the configured size limit.")
        except ValueError:
            # An invalid Content-Length is not trusted; the streaming limit still applies.
            pass

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes(chunk_size=64 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise ImageGenerationError("Cloudflare Workers AI image response exceeds the configured size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_cloudflare_error(stage: str, response: httpx.Response) -> ImageGenerationError:
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
    suffix = f"; provider_codes={codes}" if codes else ""
    logger.error(
        "image_generation stage=cloudflare outcome=failed http_status=%s provider_codes=%s",
        response.status_code,
        codes,
    )
    return ImageGenerationError(f"Cloudflare {stage} failed (HTTP {response.status_code}{suffix}).")


def generate_pin_image(*, product_name: str, product_details: str) -> dict[str, str]:
    """Generate a bounded image data URL; no separate image host is used."""
    if not settings.cloudflare_api_token or not settings.cloudflare_account_id:
        raise ImageGenerationError("Cloudflare Workers AI and account credentials are not configured.")

    max_image_bytes = settings.cloudflare_image_max_bytes
    max_base64_chars = 4 * ((max_image_bytes + 2) // 3)
    max_json_bytes = max_base64_chars + _ERROR_BODY_LIMIT
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
            with client.stream(
                "POST",
                f"{base}/ai/run/{settings.cloudflare_image_model}",
                headers={**headers, "Content-Type": "application/json"},
                json={"prompt": prompt},
            ) as generated:
                if generated.is_error:
                    error_body = _read_limited_response(generated, _ERROR_BODY_LIMIT)
                    error_response = httpx.Response(
                        status_code=generated.status_code,
                        headers=generated.headers,
                        content=error_body,
                        request=generated.request,
                    )
                    raise _safe_cloudflare_error("Workers AI generation", error_response)

                content_type = generated.headers.get("content-type", "").lower()
                if content_type.startswith("image/"):
                    image_bytes = _read_limited_response(generated, max_image_bytes)
                    image_mime = content_type.split(";", 1)[0]
                else:
                    response_bytes = _read_limited_response(generated, max_json_bytes)
                    body = json.loads(response_bytes)
                    result = body.get("result") if isinstance(body, dict) else None
                    image_value = result.get("image") if isinstance(result, dict) else None
                    if not isinstance(image_value, str) or not image_value:
                        raise ImageGenerationError("Cloudflare Workers AI returned no image data (HTTP 200).")
                    if len(image_value) > max_base64_chars:
                        raise ImageGenerationError("Cloudflare Workers AI image response exceeds the configured size limit.")
                    image_bytes = base64.b64decode(image_value, validate=True)
                    image_mime = "image/png"

                if image_mime not in {"image/png", "image/jpeg", "image/webp"}:
                    raise ImageGenerationError("Cloudflare Workers AI returned an unsupported image content type.")
                if len(image_bytes) < 1024:
                    raise ImageGenerationError("Cloudflare Workers AI returned an unexpectedly small image.")
                if len(image_bytes) > max_image_bytes:
                    raise ImageGenerationError("Cloudflare Workers AI image response exceeds the configured size limit.")

                encoded = base64.b64encode(image_bytes).decode("ascii")
                return {
                    "image_url": f"data:{image_mime};base64,{encoded}",
                    "model": settings.cloudflare_image_model,
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
