# list_product_content

- **Unique ID:** `FN-APP-MAIN-PY-022`
- **Source:** `app/main.py:503-519`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Lists saved content versions for a product. Verify product existence/access, ordering, response shape and whether any sensitive/provider metadata is exposed.

## Exact isolated source

```python
def list_product_content(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import get_product as fetch_product, list_content_versions
        if fetch_product(product_id) is None:
            raise HTTPException(status_code=404, detail="Product not found")
        rows = list_content_versions(product_id)
        return {"product_id": product_id, "versions": [_serialize_row(row) for row in rows]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Content history is unavailable. Check database migrations and connectivity.") from exc
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source.
- `VERIFIED — LINE RANGE`: isolated using neighboring definition boundaries.
- `UNVERIFIED — LOGIC`: callers, tests and edge cases still require review.
- `UNVERIFIED — LIVE BEHAVIOR`: no endpoint/provider action was executed.

## Required checks

Trace direct callees and authorization dependencies; inspect all matching tests; verify database persistence, validation, exception handling, idempotency and no unintended Pinterest side effects.
