"""Real DeepSeek Flash content generation; no fabricated fallback responses."""
from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.main import settings

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

    base_url = settings.llm_base_url.rstrip("/")
    endpoint = f"{base_url}/chat/completions"
    prompt = (
        "Create Pinterest affiliate Pin content for a USA audience in the Home Decor & Kitchen niche. "
        "Use only product facts in the supplied text and visual facts visible in the supplied image. "
        "Do not invent materials, dimensions, certifications, product performance, prices, or other claims. "
        "Return one JSON object with exactly these string keys: pin_idea, title, description, alt_text. "
        "pin_idea: a concrete visual/creative concept, max 500 characters. "
        "title: concise and relevant, max 100 characters. "
        "description: natural useful copy, avoid keyword stuffing, max 2000 characters, and include this "
        "clear disclosure verbatim: \"Affiliate disclosure: This post contains affiliate links; I may earn "
        "a commission at no extra cost to you.\" "
        "alt_text: accessibility-focused description of the actual image only, max 500 characters; "
        "if a visual detail is uncertain, leave it out. Do not put Markdown fences around the JSON.\n\n"
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
        parsed = json.loads(raw_content)
        content = GeneratedContent.model_validate(parsed)
    except ContentGenerationError:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
        # Provider error bodies can contain sensitive internals; do not relay them to API callers.
        raise ContentGenerationError("DeepSeek content generation failed or returned invalid content.") from exc

    if AFFILIATE_DISCLOSURE.lower() not in content.description.lower():
        content.description = f"{content.description.rstrip()}\n\n{AFFILIATE_DISCLOSURE}"
    if len(content.description) > 2000:
        content.description = content.description[: 2000 - len(AFFILIATE_DISCLOSURE) - 2].rstrip()
        content.description = f"{content.description}\n\n{AFFILIATE_DISCLOSURE}"
    return content, settings.llm_model
