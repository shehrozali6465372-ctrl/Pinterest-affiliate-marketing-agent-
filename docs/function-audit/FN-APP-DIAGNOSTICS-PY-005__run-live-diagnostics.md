# run_live_diagnostics

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-005`
- **Source:** `app/diagnostics.py:108-170`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Orchestrates diagnostics across configured providers. Verify which checks are invoked, side-effect guarantees, concurrency/timeout behavior and sanitized aggregation of failures.

## Exact isolated source

```python
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


class DiagnosticRunInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(default="Kitchen spice rack organizer", min_length=1, max_length=300)
    product_details: str = Field(default="A practical organizer for spices in a home kitchen.", min_length=1, max_length=1000)


@router.post("/run", dependencies=[Depends(_require_api_key)])
def run_live_diagnostics(payload: DiagnosticRunInput) -> dict[str, object]:
    """Verify live dependencies without hosting an image or publishing a Pin; provider usage may be billable."""
    from app.database import connection
    from app.credential_vault import get_pinterest_credential
    from app.media_generation import ImageGenerationError, generate_and_host_pin_image
    from app.pinterest import image_media_source
    from app.content_generation import generate_pin_content

    checks: dict[str, object] = {}
    overall_ok = True

    try:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = {"ok": True, "check": "read_only_select_1"}
    except Exception:
        checks["database"] = {"ok": False, "error": "database_connection_or_query_failed"}
        overall_ok = False

    try:
        credential = get_pinterest_credential(payload.account_id)
        with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = client.get(
                f"{settings.pinterest_api_base_url.rstrip('/')}/user_account",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
            )
        checks["pinterest"] = {"ok": response.is_success, "check": "stored_credential_user_account_read", "http_status": response.status_code}
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: source fetched from current main.
- `VERIFIED — DEFINITION ISOLATION`: one definition only.
- `UNVERIFIED — LOGIC`: full call graph, test coverage and failure handling remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic or database operation executed.

## Required checks

Inspect callers, provider/SQL contracts, test cases, timeouts, exception paths, secret redaction, read/write guarantees and cleanup behavior. No live diagnostics are triggered here.
