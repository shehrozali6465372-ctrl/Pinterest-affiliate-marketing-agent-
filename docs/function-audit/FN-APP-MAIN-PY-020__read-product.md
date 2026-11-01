# read_product

- **Unique ID:** `FN-APP-MAIN-PY-020`
- **Source:** `app/main.py:452-467`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

API handler to retrieve a product. Verify path parameter validation, not-found mapping, access control/account scoping and serialized fields.

## Exact isolated source

```python
def read_product(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import get_product as fetch_product
        row = fetch_product(product_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product persistence is unavailable. Check database connectivity and schema setup.") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_row(row)


@app.post("/products/{product_id}/content", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: boundaries checked against neighboring definitions.
- `UNVERIFIED — LOGIC`: tests, callers and behavior remain to be verified.
- `UNVERIFIED — LIVE BEHAVIOR`: no API endpoint was called.

## Required checks

Inspect request/response schema, authentication, direct callees, database query, tests, validation boundaries, failure mapping and secret/data exposure.
