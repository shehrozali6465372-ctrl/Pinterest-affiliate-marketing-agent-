"""Real DeepSeek Flash content generation; no fabricated fallback responses."""
from __future__ import annotations

import json
import logging
import re
import time

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

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


def _safe_http_failure_metadata(response: httpx.Response, elapsed_ms: int) -> dict[str, str | int]:
    """Return bounded provider diagnostics with configured credentials redacted."""
    configured_secret = settings.llm_api_key or ""

    def sanitize(value: object, limit: int) -> str:
        text = str(value)
        # Sanitize before character filtering: secrets can consist entirely of
        # otherwise-allowed characters and may be reflected by proxies/providers.
        if configured_secret:
            text = text.replace(configured_secret, "[REDACTED]")
        return re.sub(r"[^A-Za-z0-9_.:-]", "_", text)[:limit] or "unknown"

    provider_code = "unknown"
    try:
        error_body = response.json()
        error_obj = error_body.get("error", {}) if isinstance(error_body, dict) else {}
        if isinstance(error_obj, dict):
            candidate = error_obj.get("type") or error_obj.get("code")
            if isinstance(candidate, (str, int)):
                provider_code = sanitize(candidate, 80)
    except (ValueError, TypeError):
        pass
    headers = getattr(response, "headers", {})
    if hasattr(headers, "get"):
        raw_content_type = str(headers.get("content-type", "unknown"))
        if configured_secret:
            raw_content_type = raw_content_type.replace(configured_secret, "[REDACTED]")
        content_type = re.sub(r"[^A-Za-z0-9_./:-]", "_", raw_content_type)[:100] or "unknown"
    else:
        content_type = "unknown"
    raw_request_id = headers.get("x-request-id") or headers.get("request-id") if hasattr(headers, "get") else None
    request_id = sanitize(raw_request_id, 80) if raw_request_id else "unknown"
    response_bytes = len(getattr(response, "content", b"") or b"")
    return {
        "status": int(response.status_code),
        "provider_code": provider_code,
        "content_type": content_type,
        "response_bytes": response_bytes,
        "request_id": request_id,
        "duration_ms": max(0, int(elapsed_ms)),
    }


def generate_pin_content(
    *,
    product_name: str,
    product_details: str,
    image_url: str,
    _retry_attempt: int = 0,
    _retry_hint: str | None = None,
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
    if _retry_hint:
        prompt += (
            "\n\nRETRY CORRECTION: The previous response was rejected. "
            "Return a complete, syntactically valid JSON object only. Include exactly "
            "pin_idea, title, description, and alt_text as non-empty strings. "
            "Do not use Markdown fences, comments, trailing commas, or extra keys. "
            "Keep every field within its stated character limit. "
            f"Reason category: {_retry_hint}."
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
        # Thinking is enabled by default on DeepSeek Flash. For this short,
        # schema-constrained task, disable it so reasoning tokens cannot consume
        # the output budget and truncate the required JSON object.
        "thinking": {"type": "disabled"},
        "temperature": 0.4,
        "max_tokens": 2400,
        "stream": False,
    }
    request_started = time.monotonic()
    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        elapsed_ms = int((time.monotonic() - request_started) * 1000)
        metadata = _safe_http_failure_metadata(exc.response, elapsed_ms)
        if _retry_attempt == 0 and (exc.response.status_code == 429 or exc.response.status_code >= 500):
            logger.warning(
                "DeepSeek transient HTTP failure; retrying once: status=%s provider_code=%s attempt=1 duration_ms=%s content_type=%s response_bytes=%s request_id=%s",
                metadata["status"], metadata["provider_code"], metadata["duration_ms"],
                metadata["content_type"], metadata["response_bytes"], metadata["request_id"],
            )
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
            )
        # Never log request headers, API keys, prompt contents, or response bodies.
        logger.error(
            "DeepSeek HTTP failure: status=%s provider_code=%s attempt=%s duration_ms=%s content_type=%s response_bytes=%s request_id=%s",
            metadata["status"], metadata["provider_code"], _retry_attempt + 1,
            metadata["duration_ms"], metadata["content_type"], metadata["response_bytes"], metadata["request_id"],
        )
        raise ContentGenerationError(
            f"DeepSeek request rejected (HTTP {exc.response.status_code}; provider_code={metadata['provider_code']})."
        ) from exc
    except httpx.HTTPError as exc:
        if _retry_attempt == 0:
            logger.warning("DeepSeek transport failure; retrying once: exception_type=%s", type(exc).__name__)
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
            )
        logger.error("DeepSeek request transport failure: exception_type=%s", type(exc).__name__)
        raise ContentGenerationError("DeepSeek content generation request failed.") from exc

    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        if _retry_attempt == 0:
            logger.warning("DeepSeek invalid response envelope; retrying once")
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
                _retry_hint="invalid_response_envelope",
            )
        metadata = _safe_http_failure_metadata(
            response, int((time.monotonic() - request_started) * 1000)
        )
        logger.error(
            "DeepSeek API response JSON failure: status=%s content_type=%s response_bytes=%s "
            "duration_ms=%s request_id=%s",
            metadata["status"], metadata["content_type"], metadata["response_bytes"],
            metadata["duration_ms"], metadata["request_id"],
        )
        raise ContentGenerationError("DeepSeek API returned an invalid JSON response envelope.") from exc

    choices = body.get("choices") if isinstance(body, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get("message") if isinstance(choice, dict) else None
    raw_content = message.get("content") if isinstance(message, dict) else None
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None

    if not isinstance(raw_content, str):
        if _retry_attempt == 0:
            logger.warning("DeepSeek returned missing/non-text content; retrying once")
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
                _retry_hint="missing_or_non_text_content",
            )
        metadata = _safe_http_failure_metadata(
            response, int((time.monotonic() - request_started) * 1000)
        )
        logger.error(
            "DeepSeek content type failure: value_type=%s finish_reason=%s "
            "status=%s duration_ms=%s request_id=%s",
            type(raw_content).__name__, finish_reason or "unknown",
            metadata["status"], metadata["duration_ms"], metadata["request_id"],
        )
        raise ContentGenerationError("DeepSeek returned an unsupported response format.")

    try:
        parsed_content = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        if _retry_attempt == 0:
            logger.warning("DeepSeek content JSON invalid; retrying once: finish_reason=%s", finish_reason or "unknown")
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
                _retry_hint="invalid_model_json",
            )
        if finish_reason == "length":
            logger.error(
                "DeepSeek content truncated: finish_reason=length max_tokens=%s content_chars=%s",
                payload["max_tokens"],
                len(raw_content),
            )
            raise ContentGenerationError(
                "DeepSeek output reached its token limit before completing valid JSON; retry the request."
            ) from exc
        metadata = _safe_http_failure_metadata(
            response, int((time.monotonic() - request_started) * 1000)
        )
        logger.error(
            "DeepSeek model JSON parse failure: finish_reason=%s content_chars=%s "
            "status=%s duration_ms=%s request_id=%s",
            finish_reason or "unknown", len(raw_content), metadata["status"],
            metadata["duration_ms"], metadata["request_id"],
        )
        raise ContentGenerationError("DeepSeek returned invalid JSON content.") from exc

    try:
        content = GeneratedContent.model_validate(parsed_content)
    except ValidationError as exc:
        if _retry_attempt == 0:
            logger.warning("DeepSeek content schema invalid; retrying once")
            return generate_pin_content(
                product_name=product_name, product_details=product_details,
                image_url=image_url, _retry_attempt=1,
                _retry_hint="schema_validation_failed",
            )
        metadata = _safe_http_failure_metadata(
            response, int((time.monotonic() - request_started) * 1000)
        )
        logger.error(
            "DeepSeek content schema validation failure: finish_reason=%s exception_type=%s "
            "status=%s duration_ms=%s request_id=%s",
            finish_reason or "unknown", type(exc).__name__, metadata["status"],
            metadata["duration_ms"], metadata["request_id"],
        )
        raise ContentGenerationError("DeepSeek JSON did not match the required content schema.") from exc

    if AFFILIATE_DISCLOSURE.lower() not in content.description.lower():
        content.description = f"{content.description.rstrip()}\n\n{AFFILIATE_DISCLOSURE}"
    if len(content.description) > 2000:
        content.description = (
            f"{content.description[: 2000 - len(AFFILIATE_DISCLOSURE) - 2].rstrip()}\n\n"
            f"{AFFILIATE_DISCLOSURE}"
        )
    return content, settings.llm_model
