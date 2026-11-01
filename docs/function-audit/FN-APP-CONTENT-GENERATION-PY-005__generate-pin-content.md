# generate_pin_content

- **Unique ID:** `FN-APP-CONTENT-GENERATION-PY-005`
- **Definition type:** `def`
- **Source:** `app/content_generation.py:78-298`
- **Source blob SHA:** `12d8685abb2883bf4e47526aa99acffc5fd7c36c`
- **Repository snapshot:** `main@336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic overview

Flow: validates LLM_API_KEY; builds a DeepSeek chat-completions payload from product name/details and image URL; makes the outbound HTTP request; handles HTTP/transport errors with bounded retry for selected transient failures; parses provider JSON; validates GeneratedContent fields; inserts required affiliate disclosure and enforces the description limit; returns content plus model ID. Side effects: outbound DeepSeek request and bounded retry sleep.

## Inputs, outputs and failure paths

The exact signature, annotations, defaults, validators, return statements, and raises are shown in the source below. Caller-side assumptions and undocumented provider behavior are not treated as facts.

## Exact isolated source

```python
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
        retry_delay = (
            retry_delay_seconds(exc.response, _retry_attempt + 1)
            if exc.response.status_code in {500, 503} and _retry_attempt == 0
            else None
        )
        if retry_delay is not None:
            logger.warning(
                "DeepSeek transient HTTP failure; retrying once: status=%s provider_code=%s attempt=1 retry_delay_ms=%s duration_ms=%s content_type=%s response_bytes=%s request_id=%s",
                metadata["status"], metadata["provider_code"], int(retry_delay * 1000), metadata["duration_ms"],
                metadata["content_type"], metadata["response_bytes"], metadata["request_id"],
            )
            time.sleep(retry_delay)
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
        if _retry_attempt == 0 and isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            delay = retry_delay_seconds(None, _retry_attempt + 1)
            logger.warning("DeepSeek transport failure; retrying once: exception_type=%s retry_delay_ms=%s", type(exc).__name__, int(delay * 1000))
            time.sleep(delay)
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: confirmed against the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: adjacent/nested definitions are separated by indentation boundary.
- `UNVERIFIED — LOGIC CORRECTNESS`: not yet proven.
- `UNVERIFIED — TEST COVERAGE`: tests and assertions still require mapping/review.
- `UNVERIFIED — LIVE BEHAVIOR`: no runtime or provider claim is made.

## Required next checks

1. Trace direct callers and relevant dependencies.
2. Explain every statement, branch, loop, return and exception path.
3. Inspect tests and map assertions to behavior, including failure and boundary cases.
4. Review concurrency, retries, database transactions and security invariants where relevant.
5. Check the actual external API contract and side effects.
6. No production writes, credential changes, deployments or Pinterest publishing during this audit.
