# run_live_diagnostics

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-005`
- **Source:** `app/diagnostics.py:144-242`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Orchestrates the selected diagnostic checks and aggregates structured outcomes. Verify request options, which providers run, read-only guarantees, bounded execution, exception isolation and whether optional checks are truly skipped.

## Exact isolated source

```python
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
        if not response.is_success:
            overall_ok = False
    except LookupError:
        checks["pinterest"] = {"ok": False, "error": "credential_not_connected"}
        overall_ok = False
    except Exception:
        checks["pinterest"] = {"ok": False, "error": "credential_decryption_or_request_failed"}
        overall_ok = False

    media = None
    # Avoid billable generation/upload if critical read-only connectivity checks fail.
    prerequisites_ok = bool(checks.get("database", {}).get("ok") and checks.get("pinterest", {}).get("ok"))
    if prerequisites_ok:
        try:
            media = generate_and_host_pin_image(product_name=payload.product_name, product_details=payload.product_details)
            media_source = image_media_source(media["image_url"])
            checks["cloudflare_image_generation"] = {
                "ok": bool(media.get("image_url")) and media_source.get("source_type") == "image_base64",
                "model": media.get("model"),
                "media_source_type": media_source.get("source_type"),
                "image_bytes_persisted": False,
                "uploaded_to_cloudflare_images": False,
            }
            if not checks["cloudflare_image_generation"]["ok"]:
                overall_ok = False
        except ImageGenerationError as exc:
            checks["cloudflare_image_generation"] = {"ok": False, "error": str(exc)[:180]}
            overall_ok = False
        except Exception:
            checks["cloudflare_image_generation"] = {"ok": False, "error": "image_generation_or_media_validation_failed"}
            overall_ok = False
    else:
        checks["cloudflare_image_generation"] = {
            "ok": False, "skipped": True, "error": "database_or_pinterest_check_failed",
        }

    if media and settings.llm_api_key:
        try:
            generated, model_id = generate_pin_content(
                product_name=payload.product_name,
                product_details=payload.product_details,
                image_url=media["image_url"],
            )
            ok = bool(generated.title and generated.description and generated.alt_text)
            checks["deepseek_multimodal_generation"] = {
                "ok": ok, "model": model_id,
                "title_returned": bool(generated.title),
                "description_returned": bool(generated.description),
                "alt_text_returned": bool(generated.alt_text),
            }
            overall_ok = overall_ok and ok
        except Exception:
            checks["deepseek_multimodal_generation"] = {"ok": False, "error": "deepseek_multimodal_completion_failed"}
            overall_ok = False
    else:
        checks["deepseek_multimodal_generation"] = {"ok": False, "error": "llm_key_missing_or_image_generation_failed"}
        overall_ok = False

    return {
        "ok": overall_ok,
        "checks": checks,
        "side_effects": {
            "pinterest_pin_created": False,
            "pinterest_board_created": False,
            "product_persisted": False,
            "cloudflare_test_image_uploaded": False,
            "generated_image_persisted": False,
            "provider_usage_may_be_billable": bool(prerequisites_ok),
        },
        "secrets_returned": False,
    }
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact current source blob fetched.
- `VERIFIED — CORRECTED LINE RANGE`: range checked against all definitions in diagnostics.py.
- `UNVERIFIED — LOGIC`: call graph, tests and runtime behavior remain to be proven.
- `UNVERIFIED — LIVE STATE`: no live diagnostic was run.

## Required checks

Inspect all callers, API and DB dependencies, tests, timeout/exception behavior, read-only side effects and redaction. Do not run this diagnostic against production during the audit.
