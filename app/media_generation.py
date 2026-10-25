"""Cloudflare Workers AI image generation and Cloudflare Images hosting.

Requires a Cloudflare API token with Workers AI Run and Cloudflare Images Write
permissions. Images are generated server-side and uploaded to the account's Images
service; the returned variant URL is the durable public URL used by Pinterest.
"""
from __future__ import annotations

import httpx

from app.config import settings


class ImageGenerationError(RuntimeError):
    """Raised when image generation or public hosting cannot be verified."""


def _safe_cloudflare_error(stage: str, response: httpx.Response) -> ImageGenerationError:
    """Expose only HTTP status and provider error codes; never log credentials or full bodies."""
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
    return ImageGenerationError(f"Cloudflare {stage} failed (HTTP {response.status_code}{suffix}).")


def generate_and_host_pin_image(*, product_name: str, product_details: str) -> dict[str, str]:
    if not settings.cloudflare_api_token or not settings.cloudflare_account_id:
        raise ImageGenerationError("Cloudflare Workers AI and account credentials are not configured.")

    prompt = (
        "Create a polished, realistic vertical 2:3 Pinterest product lifestyle image for a USA "
        "home organization audience. Feature the following product accurately, with no logos, "
        "watermarks, fabricated text, extra product features, or misleading claims. Use a clean, "
        "bright, editorial kitchen setting, balanced composition, and clear product visibility. "
        "Do not add typography. Product: "
        f"{product_name}. Verified details: {product_details[:2500]}"
    )
    headers = {"Authorization": f"Bearer {settings.cloudflare_api_token}"}
    timeout = httpx.Timeout(90.0, connect=10.0)
    base = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}"

    try:
        with httpx.Client(timeout=timeout) as client:
            generated = client.post(
                f"{base}/ai/run/{settings.cloudflare_image_model}",
                headers={**headers, "Content-Type": "application/json"},
                json={"prompt": prompt},
            )
            if generated.is_error:
                raise _safe_cloudflare_error("Workers AI generation", generated)
            content_type = generated.headers.get("content-type", "").lower()
            image_bytes: bytes
            if "image/" in content_type:
                image_bytes = generated.content
                image_mime = content_type.split(";", 1)[0]
            else:
                body = generated.json()
                result = body.get("result") if isinstance(body, dict) else None
                image_value = result.get("image") if isinstance(result, dict) else None
                if not isinstance(image_value, str) or not image_value:
                    raise ImageGenerationError("Cloudflare Workers AI returned no image data (HTTP 200).")
                import base64
                image_bytes = base64.b64decode(image_value, validate=True)
                image_mime = "image/png"

            if len(image_bytes) < 1024:
                raise ImageGenerationError("Cloudflare Workers AI returned an unexpectedly small image.")

            uploaded = client.post(
                f"{base}/images/v1",
                headers=headers,
                files={"file": ("pinterest-pin.png", image_bytes, image_mime)},
                data={"requireSignedURLs": "false"},
            )
            if uploaded.is_error:
                raise _safe_cloudflare_error("Images upload", uploaded)
            upload_body = uploaded.json()
            result = upload_body.get("result") if isinstance(upload_body, dict) else None
            variants = result.get("variants") if isinstance(result, dict) else None
            if not isinstance(variants, list) or not variants or not isinstance(variants[0], str):
                raise ImageGenerationError("Cloudflare Images returned no public image variant URL (HTTP 200).")
            image_url = variants[0]
            if not image_url.startswith("https://"):
                raise ImageGenerationError("Cloudflare Images returned a non-HTTPS URL.")
            return {
                "image_url": image_url,
                "image_id": str(result.get("id") or ""),
                "model": settings.cloudflare_image_model,
            }
    except ImageGenerationError:
        raise
    except httpx.TimeoutException as exc:
        raise ImageGenerationError("Cloudflare image request timed out; check provider latency and retry budget.") from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(f"Cloudflare image request failed ({type(exc).__name__}).") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise ImageGenerationError(f"Cloudflare returned an invalid image response ({type(exc).__name__}).") from exc
