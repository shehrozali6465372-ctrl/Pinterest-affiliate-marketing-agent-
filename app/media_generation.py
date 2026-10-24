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
            generated.raise_for_status()
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
                    raise ImageGenerationError("Cloudflare AI returned no image bytes.")
                import base64
                image_bytes = base64.b64decode(image_value, validate=True)
                image_mime = "image/png"

            if len(image_bytes) < 1024:
                raise ImageGenerationError("Cloudflare AI returned an unexpectedly small image.")

            uploaded = client.post(
                f"{base}/images/v1",
                headers=headers,
                files={"file": ("pinterest-pin.png", image_bytes, image_mime)},
                data={"requireSignedURLs": "false"},
            )
            uploaded.raise_for_status()
            upload_body = uploaded.json()
            result = upload_body.get("result") if isinstance(upload_body, dict) else None
            variants = result.get("variants") if isinstance(result, dict) else None
            if not isinstance(variants, list) or not variants or not isinstance(variants[0], str):
                raise ImageGenerationError("Cloudflare Images did not return a public image variant URL.")
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
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise ImageGenerationError("Cloudflare image generation or hosting failed.") from exc
