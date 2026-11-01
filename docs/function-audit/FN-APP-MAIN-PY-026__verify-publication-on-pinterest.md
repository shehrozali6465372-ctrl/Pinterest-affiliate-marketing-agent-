# verify_publication_on_pinterest

- **Unique ID:** `FN-APP-MAIN-PY-026`
- **Source:** `app/main.py:553-598`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Read-only verification path. It queries Pinterest for a Pin and compares returned Pin data with stored publication evidence. Confirm exact endpoint, account token source, board ownership checks, pagination and which fields are compared; a successful GET is not automatically proof that the expected affiliate URL is present.

## Exact isolated source

```python
def verify_publication_on_pinterest(publication_id: int) -> dict[str, object]:
    """Read-only board pagination and Pin detail verification for an existing record."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    from app.database import get_publication
    from app.credential_vault import get_pinterest_credential
    from app.pinterest import PinterestReadError, get_pin_read_only, list_board_pins_read_only
    try:
        publication = get_publication(publication_id)
        if publication is None:
            raise HTTPException(status_code=404, detail="Publication not found")
        account_id = publication.get("account_id")
        board_id = publication.get("board_id")
        if not account_id or not board_id:
            raise HTTPException(status_code=409, detail="Publication lacks the account or board reference required for verification")
        credential = get_pinterest_credential(str(account_id))
        board_result = list_board_pins_read_only(board_id=str(board_id), access_token=credential["access_token"])
        pins = board_result["items"]
        expected_pin_id = publication.get("pinterest_pin_id")
        matching_pin = next((pin for pin in pins if str(pin.get("id")) == str(expected_pin_id)), None) if expected_pin_id else None
        detail = None
        if matching_pin is not None:
            detail = get_pin_read_only(pin_id=str(expected_pin_id), access_token=credential["access_token"])
        # Return only operator-relevant Pin fields; never return credential material or raw provider bodies.
        safe_pins = [{key: pin.get(key) for key in ("id", "board_id", "title", "description", "link", "created_at")} for pin in pins]
        detail_matches = bool(detail and str(detail.get("id")) == str(expected_pin_id) and str(detail.get("board_id")) == str(board_id))
        return {
            "publication_id": publication_id, "publication_status": publication.get("status"),
            "account_id": account_id, "board_id": board_id,
            "board_pages_read": board_result["pages_read"],
            "board_pins_seen": len(safe_pins), "pagination_complete": board_result["pagination_complete"],
            "stored_pin_id": expected_pin_id, "stored_pin_found_on_board": matching_pin is not None,
            "pin_detail_board_matches": detail_matches, "pins": safe_pins,
            "read_only": True,
        }
    except HTTPException:
        raise
    except PinterestReadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Stored Pinterest account credential is unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Pinterest publication verification could not be completed") from exc


@app.post("/publications/{publication_id}/reconcile", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob retrieved.
- `VERIFIED — LINE RANGE`: isolated by Python definition boundary.
- `UNVERIFIED — LOGIC`: complete call graph, edge cases and tests not yet proven.
- `UNVERIFIED — LIVE BEHAVIOR`: no live endpoint or Pinterest operation invoked.

## Required checks

Trace all callees and route dependencies; inspect associated tests; verify request validation, authorization, idempotency, DB transaction outcomes, Pinterest response parsing, uncertainty handling and affiliate-link preservation. Any publish-capable call must remain unexecuted in this read-only task.
