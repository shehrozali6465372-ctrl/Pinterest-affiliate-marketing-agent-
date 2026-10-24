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
    # DeepSeek Flash supports image input. Use the generated image as visual evidence
    # for accessible alt text, while restricting product claims to supplied facts.
    prompt = (
        "Create Pinterest affiliate Pin content for a USA audience in the Home Decor & Kitchen niche. "
        "You can inspect the supplied image. Use visible evidence for alt_text, but use only supplied product "
        "facts for claims about materials, dimensions, certifications, performance, prices, or specifications. "
        "Do not infer hidden properties or invent unsupported claims. "
        "Return one JSON object with exactly these string keys: pin_idea, title, description, alt_text. "
        "pin_idea: a concrete visual/creative concept consistent with the product details, max 500 characters. "
        "title: concise and relevant, max 100 characters. "
        "description: natural useful copy, avoid keyword stuffing, max 2000 characters, and include this "
        "clear disclosure verbatim: \"Affiliate disclosure: This post contains affiliate links; I may earn "
        "a commission at no extra cost to you.\" "
        "alt_text: concise accessibility-focused description of visible image content, max 500 characters; "
        "describe only what is actually visible. Do not put Markdown fences around the JSON.\n\n"
        f"Product name: {product_name}\nProduct details: {product_details}"
    )
    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "You produce accurate, accessible Pinterest copy and follow requested JSON output exactly.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
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
