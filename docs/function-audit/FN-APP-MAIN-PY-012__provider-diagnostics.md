# provider_diagnostics

- **Unique ID:** `FN-APP-MAIN-PY-012`
- **Source:** `app/main.py:149-211`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Aggregates provider diagnostics for configured services. Verify that checks are read-only, which external endpoints are called, credential selection, timeout/retry policy, status normalization and absence of token leakage.

## Exact isolated source

```python
def provider_diagnostics() -> dict[str, object]:
    """Check provider credentials with non-generation requests; never return secrets."""
    import httpx

    result: dict[str, object] = {
        "deepseek": {"configured": bool(settings.llm_api_key), "verified": False},
        "cloudflare": {
            "token_configured": bool(settings.cloudflare_api_token),
            "account_id_configured": bool(settings.cloudflare_account_id),
            "verified": False,
        },
        "note": "Credential/API access check only. This endpoint does not generate an image or billable LLM completion.",
    }
    timeout = httpx.Timeout(12.0, connect=5.0)

    if settings.llm_api_key:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(
                    f"{settings.llm_base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                )
            result["deepseek"] = {
                "configured": True,
                "verified": response.is_success,
                "http_status": response.status_code,
                "check": "models_endpoint",
            }
        except httpx.HTTPError:
            result["deepseek"] = {
                "configured": True,
                "verified": False,
                "error": "provider_unreachable_or_request_failed",
            }

    if settings.cloudflare_api_token and settings.cloudflare_account_id:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(
                    "https://api.cloudflare.com/client/v4/accounts/"
                    f"{settings.cloudflare_account_id}/ai/models/search",
                    headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
                    params={"per_page": 1},
                )
            result["cloudflare"] = {
                "token_configured": True,
                "account_id_configured": True,
                "verified": response.is_success,
                "http_status": response.status_code,
                "check": "workers_ai_models_endpoint",
            }
        except httpx.HTTPError:
            result["cloudflare"] = {
                "token_configured": True,
                "account_id_configured": True,
                "verified": False,
                "error": "provider_unreachable_or_request_failed",
            }

    return result


@app.post("/integrations/pinterest/credentials", status_code=status.HTTP_201_CREATED)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact code fetched from recorded blob.
- `VERIFIED — SOURCE RANGE`: requested source line range isolated.
- `UNVERIFIED — LOGIC`: caller graph, tests and edge cases remain.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live API, OAuth or DB operation was executed.

## Required checks

Trace authentication dependencies and every downstream function. Inspect positive/negative tests, exception paths, provider contracts, timeouts, retries, persistence atomicity and redaction. No production token or state changes.
