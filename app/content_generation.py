"""Real DeepSeek Flash content generation; no fabricated fallback responses."""
from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings

PROMPT_VERSION = "pin-content-v1"
AFFILIATE_DISCLOSURE = (
    "Affiliate disclosure: This post contains affiliate links; "
    "I may earn a commission at no extra cost to you."
)


class GeneratedContent(BaseModel):
    pin_idea: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    alt_text: str = Field(min_length=1, max_length=500)


class ContentGenerationError(RuntimeError):
    """Raised when the real provider cannot return valid content."""


def generate_pin_content(
    *,
    product_name: str,
    product_details: str,
    image_url: str,
) -> tuple[GeneratedContent, str]:
    """Generate content with DeepSeek Flash using supplied text and image evidence."""
    if not settings.llm_api_key:
        raise ContentGenerationError("LLM_API_KEY is not configured; content generation is unavailable.")

    endpoint = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    # DeepSeek chat models are text-only; do not send OpenAI-style image_url content
    # that the provider may reject. Ground every generated claim in supplied product
    # text and have the owner verify alt text against the generated image.
    prompt = (
        "Create Pinterest affiliate Pin content for a USA audience in the Home Decor & Kitchen niche. "
        "You are receiving text only, not the image itself. Use only product facts in the supplied text. "
        "Do not claim to have inspected the image and do not invent materials, dimensions, certifications, "
        "product performance, prices, colors, or other unsupported claims. "
        "Return one JSON object with exactly these string keys: pin_idea, title, description, alt_text. "
        "pin_idea: a concrete visual/creative concept consistent with the product details, max 500 characters. "
        "title: concise and relevant, max 100 characters. "
        "description: natural useful copy, avoid keyword stuffing, max 2000 characters, and include this "
        "clear disclosure verbatim: \"Affiliate disclosure: This post contains affiliate links; I may earn "
        "a commission at no extra cost to you.\" "
        "alt_text: a cautious accessibility-focused draft based only on the supplied product facts and intended "
        "image concept, max 500 characters; do not assert unverified visual details. It must be checked against "
        "the final image before publication. Do not put Markdown fences around the JSON.\n\n"
        f"Product name: {product_name}\nProduct details: {product_details}"
    )
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "You produce accurate, accessible Pinterest copy and follow requested JSON output exactly.",
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
        "max_tokens": 1200,
        "stream": False,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        body = response.json()
        raw_content = body["choices"][0]["message"]["content"]
        if not isinstance(raw_content, str):
            raise ContentGenerationError("LLM returned an unsupported response format.")
        content = GeneratedContent.model_validate(json.loads(raw_content))
    except ContentGenerationError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
        raise ContentGenerationError(
            "DeepSeek content generation failed or returned invalid content."
        ) from exc

    if AFFILIATE_DISCLOSURE.lower() not in content.description.lower():
        content.description = f"{content.description.rstrip()}\n\n{AFFILIATE_DISCLOSURE}"
    if len(content.description) > 2000:
        content.description = (
            f"{content.description[: 2000 - len(AFFILIATE_DISCLOSURE) - 2].rstrip()}\n\n"
            f"{AFFILIATE_DISCLOSURE}"
        )
    return content, settings.llm_model
