# readiness

- **Unique ID:** `FN-APP-MAIN-PY-011`
- **Source:** `app/main.py:121-148`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Readiness endpoint probes required dependencies/configuration and returns a readiness state. Distinguish configuration presence from actual provider/database reachability; verify which probes run, timeouts, secret redaction and whether endpoint can cause billable/provider side effects.

## Exact isolated source

```python
def readiness() -> dict[str, object]:
    legacy_pinterest_configured = bool(
        settings.pinterest_access_token and settings.pinterest_board_id
    )
    from app.credential_vault import token_encryption_key_is_valid

    encryption_key_valid = token_encryption_key_is_valid()
    account_workflow_configured = bool(settings.database_url and encryption_key_valid)
    credential_ingest_configured = bool(settings.pinterest_credential_ingest_key)
    return {
        "database_configured": bool(settings.database_url),
        # Backwards-compatible field: this refers only to the legacy direct-token publish route.
        "pinterest_configured": legacy_pinterest_configured,
        "pinterest_legacy_direct_configured": legacy_pinterest_configured,
        # Publishing from a stored OAuth credential needs DB + encryption; this does not prove account connection.
        "pinterest_account_workflow_configured": account_workflow_configured,
        "pinterest_token_encryption_key_valid": encryption_key_valid,
        # Hub-to-agent OAuth credential ingestion is a separate service-to-service path.
        "pinterest_credential_ingest_configured": credential_ingest_configured,
        "image_generation_configured": bool(settings.cloudflare_api_token and settings.cloudflare_account_id),
        "llm_configured": bool(settings.llm_api_key),
        "llm_model": settings.llm_model if settings.llm_api_key else None,
        "api_key_configured": bool(settings.app_api_key),
        "note": "Configuration presence does not prove credentials, account connection, access, or permissions are valid.",
    }


@app.get("/diagnostics/providers", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact code fetched from recorded blob.
- `VERIFIED — SOURCE RANGE`: requested source line range isolated.
- `UNVERIFIED — LOGIC`: caller graph, tests and edge cases remain.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live API, OAuth or DB operation was executed.

## Required checks

Trace authentication dependencies and every downstream function. Inspect positive/negative tests, exception paths, provider contracts, timeouts, retries, persistence atomicity and redaction. No production token or state changes.
