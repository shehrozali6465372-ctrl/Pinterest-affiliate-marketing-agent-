# pinterest_read_only_diagnostic

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-003`
- **Source:** `app/diagnostics.py:50-93`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Performs a read-only Pinterest credential/API diagnostic. Verify exact endpoint and scopes, token retrieval/redaction, no board/pin creation, bounded timeout and response handling.

## Exact isolated source

```python
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
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: source fetched from current main.
- `VERIFIED — DEFINITION ISOLATION`: one definition only.
- `UNVERIFIED — LOGIC`: full call graph, test coverage and failure handling remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic or database operation executed.

## Required checks

Inspect callers, provider/SQL contracts, test cases, timeouts, exception paths, secret redaction, read/write guarantees and cleanup behavior. No live diagnostics are triggered here.
