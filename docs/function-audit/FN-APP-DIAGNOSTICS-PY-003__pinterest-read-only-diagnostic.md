# pinterest_read_only_diagnostic

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-003`
- **Source:** `app/diagnostics.py:48-136`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Loads a stored Pinterest credential and performs read-only API checks. Verify exact endpoint, no create/update/delete calls, token scope, timeout, response parsing and secret redaction.

## Exact isolated source

```python
def pinterest_read_only_diagnostic(
    account_id: str = Query(..., min_length=1, max_length=200),
) -> dict[str, object]:
    """Verify one stored Pinterest credential with a read-only account lookup.

    The account ID must come from the authorized caller; this endpoint must not
    silently check a hard-coded user's credential.
    """
    from app.credential_vault import TokenEncryptionConfigurationError, get_pinterest_credential
    from app.database import DatabaseConfigurationError

    side_effects = {
        "database_modified": False,
        "pinterest_pin_created": False,
        "pinterest_board_created": False,
        "ai_generation_called": False,
        "image_generation_called": False,
    }

    # Separate vault failures from Pinterest HTTP failures without returning
    # exception text, token material, or other secrets.
    try:
        credential = get_pinterest_credential(account_id)
    except LookupError:
        return {
            "ok": False,
            "stage": "credential_vault",
            "error": "credential_not_connected",
            "side_effects": side_effects,
        }
    except InvalidTag:
        raise HTTPException(
            status_code=503,
            detail={"stage": "credential_decryption", "error": "credential_decryption_failed"},
        ) from None
    except TokenEncryptionConfigurationError:
        raise HTTPException(
            status_code=503,
            detail={"stage": "credential_configuration", "error": "token_encryption_key_missing_or_invalid"},
        ) from None
    except DatabaseConfigurationError:
        raise HTTPException(
            status_code=503,
            detail={"stage": "database_configuration", "error": "database_url_missing_or_invalid"},
        ) from None
    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail={"stage": "database", "error": "credential_database_query_failed"},
        ) from None
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"stage": "credential_vault", "error": "credential_lookup_or_decryption_failed"},
        ) from None

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = client.get(
                f"{settings.pinterest_api_base_url.rstrip('/')}/user_account",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
            )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503,
            detail={"stage": "pinterest_request", "error": "pinterest_api_unreachable"},
        ) from None

    if not response.is_success:
        status_code = 401 if response.status_code in (401, 403) else 502
        raise HTTPException(
            status_code=status_code,
            detail={
                "stage": "pinterest_api",
                "error": "pinterest_api_rejected_credential_or_request",
                "upstream_http_status": response.status_code,
            },
        )

    return {
        "ok": True,
        "stage": "pinterest_api",
        "check": "stored_credential_user_account_read",
        "http_status": response.status_code,
        "account_id": account_id,
        "side_effects": side_effects,
    }
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — CORRECTED LINE RANGE`: range checked against all definitions in diagnostics.py.
- `UNVERIFIED — LOGIC`: call graph, tests and runtime behavior remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic was run.

## Required checks

Inspect all callers, API and DB dependencies, tests, timeout/exception behavior, read-only side effects and redaction. Do not run this diagnostic against production during the audit.
