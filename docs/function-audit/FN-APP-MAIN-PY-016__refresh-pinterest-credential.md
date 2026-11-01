# refresh_pinterest_credential

- **Unique ID:** `FN-APP-MAIN-PY-016`
- **Source:** `app/main.py:251-377`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Refresh-token lifecycle handler. Verify token exchange endpoint, refresh token rotation, expiry parsing, persistence order, lock/concurrency behavior, rollback if new token storage fails, and whether invalid_grant forces reconnect. Never run against production credentials in this audit.

## Exact isolated source

```python
def refresh_pinterest_credential(
    payload: PinterestRefreshInput,
    x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key"),
) -> dict[str, object]:
    """Refresh an expired Pinterest access token using server-to-server app credentials."""
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")

    from datetime import datetime, timedelta, timezone
    import httpx
    from cryptography.exceptions import InvalidTag
    from app.credential_vault import (
        TokenEncryptionConfigurationError,
        get_pinterest_refresh_credential,
        store_pinterest_credential,
    )
    from app.database import DatabaseConfigurationError

    try:
        stored = get_pinterest_refresh_credential(payload.account_id)
    except LookupError:
        raise HTTPException(status_code=409, detail="No usable Pinterest refresh token is stored; reconnect Pinterest.") from None
    except InvalidTag:
        raise HTTPException(status_code=503, detail="Stored Pinterest refresh token failed authenticated decryption.") from None
    except TokenEncryptionConfigurationError:
        raise HTTPException(status_code=503, detail="Pinterest token encryption is not configured correctly.") from None
    except DatabaseConfigurationError:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured correctly.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Pinterest refresh credential lookup failed.") from None

    # Avoid sending a refresh token to Pinterest after its declared expiry.
    # Null expiry remains supported for older stored credentials; malformed expiry fails closed.
    stored_refresh_expiry = stored.get("refresh_token_expires_at")
    if stored_refresh_expiry is not None:
        try:
            if not isinstance(stored_refresh_expiry, datetime):
                stored_refresh_expiry = datetime.fromisoformat(
                    str(stored_refresh_expiry).replace("Z", "+00:00")
                )
            if stored_refresh_expiry.tzinfo is None:
                stored_refresh_expiry = stored_refresh_expiry.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            raise HTTPException(
                status_code=503,
                detail="Stored Pinterest refresh-token expiry is invalid; reconnect the account.",
            ) from None
        if stored_refresh_expiry <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=409,
                detail="Stored Pinterest refresh token has expired; reconnect the account.",
            )

    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=8.0)) as client:
            response = client.post(
                f"{settings.pinterest_api_base_url.rstrip('/')}/oauth/token",
                auth=(payload.client_id, payload.client_secret),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": stored["refresh_token"],
                    "continuous_refresh": "true",
                },
            )
        token_data = response.json() if response.content else {}
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Pinterest OAuth token refresh request failed.") from None

    if not response.is_success or not isinstance(token_data, dict) or not token_data.get("access_token"):
        status_code = 401 if response.status_code in (400, 401, 403) else 502
        raise HTTPException(
            status_code=status_code,
            detail="Pinterest rejected token refresh. Reconnect the account if the refresh token is invalid or expired.",
        )

    now = datetime.now(timezone.utc)
    expires_at = (
        (now + timedelta(seconds=int(token_data["expires_in"]))).isoformat()
        if token_data.get("expires_in") is not None else None
    )
    refresh_expiry = token_data.get("refresh_token_expires_at")
    if refresh_expiry is not None:
        try:
            refresh_token_expires_at = datetime.fromtimestamp(float(refresh_expiry), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError):
            refresh_token_expires_at = None
    elif token_data.get("refresh_token_expires_in") is not None:
        refresh_token_expires_at = (
            now + timedelta(seconds=int(token_data["refresh_token_expires_in"]))
        ).isoformat()
    else:
        # A successful refresh may omit refresh-token expiry metadata. Preserve
        # the previously stored expiry rather than reporting it as unknown.
        refresh_token_expires_at = stored.get("refresh_token_expires_at")

    try:
        saved = store_pinterest_credential({
            "account_id": stored["account_id"],
            "pinterest_user_id": stored["pinterest_user_id"],
            "username": stored.get("username") or "",
            "access_token": str(token_data["access_token"]),
            # Pinterest may omit a rotated refresh token; never erase the still-valid stored one.
            "refresh_token": str(token_data.get("refresh_token") or stored.get("refresh_token") or ""),
            "token_type": str(token_data.get("token_type") or "bearer"),
            "scope": str(token_data.get("scope") or stored.get("scope") or ""),
            "expires_at": expires_at,
            "refresh_token_expires_at": refresh_token_expires_at,
        })
    except Exception:
        raise HTTPException(status_code=503, detail="Pinterest refreshed a token but encrypted persistence could not be confirmed.") from None

    return {
        "refreshed": True,
        "account_id": saved["account_id"],
        "expires_at": saved.get("expires_at").isoformat() if saved.get("expires_at") else expires_at,
        "refresh_token_expires_at": (
            saved.get("refresh_token_expires_at").isoformat()
            if saved.get("refresh_token_expires_at")
            else refresh_token_expires_at.isoformat()
            if isinstance(refresh_token_expires_at, datetime)
            else refresh_token_expires_at
        ),
    }


@app.post("/integrations/pinterest/operation")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact code fetched from recorded blob.
- `VERIFIED — SOURCE RANGE`: requested source line range isolated.
- `UNVERIFIED — LOGIC`: caller graph, tests and edge cases remain.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live API, OAuth or DB operation was executed.

## Required checks

Trace authentication dependencies and every downstream function. Inspect positive/negative tests, exception paths, provider contracts, timeouts, retries, persistence atomicity and redaction. No production token or state changes.
