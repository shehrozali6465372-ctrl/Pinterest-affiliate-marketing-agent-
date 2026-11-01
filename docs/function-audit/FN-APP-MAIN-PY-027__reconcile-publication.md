# reconcile_publication

- **Unique ID:** `FN-APP-MAIN-PY-027`
- **Source:** `app/main.py:599-626`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Reconciliation handler for a publication with uncertain outcome. It requires nonblank evidence fields and delegates to DB reconciliation logic. Verify which evidence is trusted, whether Pinterest is queried before state transition, and whether status changes can incorrectly mark an unknown publish as succeeded.

## Exact isolated source

```python
def reconcile_publication(publication_id: int, payload: PublicationReconciliationInput) -> dict[str, object]:
    """Operator-confirmed resolution of an `unknown` publish result; never publishes a Pin."""
    if publication_id <= 0:
        raise HTTPException(status_code=422, detail="publication_id must be positive")
    if payload.outcome == "succeeded" and not payload.pinterest_pin_id:
        raise HTTPException(status_code=422, detail="Verified Pinterest Pin ID is required when outcome is succeeded")
    if payload.outcome == "failed" and payload.pinterest_pin_id:
        raise HTTPException(status_code=422, detail="Do not provide a Pin ID when confirming no Pin exists")
    from app.database import reconcile_unknown_publication
    try:
        row = reconcile_unknown_publication(
            publication_id, outcome=payload.outcome,
            pinterest_pin_id=payload.pinterest_pin_id,
            operator_evidence=payload.operator_evidence,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Publication not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publication reconciliation failed; inspect the stored record before retrying") from exc
    for field in ("created_at", "updated_at"):
        if row.get(field) is not None:
            row[field] = row[field].isoformat()
    return {"reconciled": True, "published": row.get("status") == "succeeded", "publication": row}


@app.post("/products/{product_id}/content/{content_version_id}/publish", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob retrieved.
- `VERIFIED — LINE RANGE`: isolated by Python definition boundary.
- `UNVERIFIED — LOGIC`: complete call graph, edge cases and tests not yet proven.
- `UNVERIFIED — LIVE BEHAVIOR`: no live endpoint or Pinterest operation invoked.

## Required checks

Trace all callees and route dependencies; inspect associated tests; verify request validation, authorization, idempotency, DB transaction outcomes, Pinterest response parsing, uncertainty handling and affiliate-link preservation. Any publish-capable call must remain unexecuted in this read-only task.
