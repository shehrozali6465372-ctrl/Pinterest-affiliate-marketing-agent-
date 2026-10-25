"""Cloudflare Workers AI image generation without a separate image-hosting service.
Generated images are returned as data URLs and sent to Pinterest using image_base64.
"""
from __future__ import annotations
import base64
import httpx
from app.config import settings

class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or returns unusable data."""

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
    return ImageGenerationError(f"Cloudflare {stage} failed (HTTP {response.status_code}{suffix}).")

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
            generated = client.post(
                f"{base}/ai/run/{settings.cloudflare_image_model}",
                headers={**headers, "Content-Type": "application/json"},
                json={"prompt": prompt},
            )
            if generated.is_error:
                raise _safe_cloudflare_error("Workers AI generation", generated)
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
        raise ImageGenerationError("Cloudflare image generation timed out; check provider latency and retry budget.") from exc
    except httpx.HTTPError as exc:
        raise ImageGenerationError(f"Cloudflare image generation request failed ({type(exc).__name__}).") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise ImageGenerationError(f"Cloudflare returned an invalid image response ({type(exc).__name__}).") from exc
