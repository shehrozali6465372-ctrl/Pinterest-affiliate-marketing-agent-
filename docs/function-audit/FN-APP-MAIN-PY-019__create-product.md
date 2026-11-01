# create_product

- **Unique ID:** `FN-APP-MAIN-PY-019`
- **Source:** `app/main.py:435-451`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

API handler to create a product record. Trace auth dependency, request model, database function, idempotency behavior and response serialization.

## Exact isolated source

```python
def create_product(product: ProductInput) -> dict[str, object]:
    try:
        from app.database import create_product as save_product
        row = save_product(
            product_name=product.product_name,
            product_details=product.product_details,
            image_url=str(product.image_url),
            affiliate_url=product.affiliate_url,
        )
        return _serialize_row(row)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Product persistence is unavailable. Apply database migrations and check database connectivity.") from exc


@app.get("/products/{product_id}", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: boundaries checked against neighboring definitions.
- `UNVERIFIED — LOGIC`: tests, callers and behavior remain to be verified.
- `UNVERIFIED — LIVE BEHAVIOR`: no API endpoint was called.

## Required checks

Inspect request/response schema, authentication, direct callees, database query, tests, validation boundaries, failure mapping and secret/data exposure.
