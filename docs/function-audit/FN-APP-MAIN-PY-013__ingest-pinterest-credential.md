# ingest_pinterest_credential

- **Unique ID:** `FN-APP-MAIN-PY-013`
- **Source:** `app/main.py:212-237`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Accepts Pinterest OAuth credential handoff and stores it through encrypted credential vault. Verify caller authentication, account/user identity validation, token encryption before persistence, duplicate account semantics and response redaction. No credential was submitted during this audit.

## Exact isolated source

```python
def ingest_pinterest_credential(
    payload: PinterestCredentialInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Accept Pinterest OAuth credentials from the trusted Modern Living Hub backend only."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")
    if not settings.pinterest_token_encryption_key:
        raise HTTPException(status_code=503, detail="Pinterest credential encryption is not configured.")
    try:
        from app.credential_vault import store_pinterest_credential
        saved = store_pinterest_credential(payload.model_dump())
        return {
            "stored": True,
            "account_id": saved["account_id"],
            "pinterest_user_id": saved["pinterest_user_id"],
            "status": saved["status"],
            "updated_at": saved["updated_at"].isoformat() if saved.get("updated_at") else None,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Credential storage failed; no token values were returned.") from exc
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact code fetched from recorded blob.
- `VERIFIED — SOURCE RANGE`: requested source line range isolated.
- `UNVERIFIED — LOGIC`: caller graph, tests and edge cases remain.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live API, OAuth or DB operation was executed.

## Required checks

Trace authentication dependencies and every downstream function. Inspect positive/negative tests, exception paths, provider contracts, timeouts, retries, persistence atomicity and redaction. No production token or state changes.
