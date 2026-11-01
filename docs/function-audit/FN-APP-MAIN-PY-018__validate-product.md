# validate_product

- **Unique ID:** `FN-APP-MAIN-PY-018`
- **Source:** `app/main.py:424-434`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Validates product request fields before persistence or generation. Verify required fields, length limits, whitespace normalization and affiliate URL validator integration.

## Exact isolated source

```python
def validate_product(product: ProductInput) -> dict[str, object]:
    return {
        "valid": True,
        "product_name": product.product_name,
        "image_url": str(product.image_url),
        "affiliate_url": product.affiliate_url,
        "next_step": "Validation only; this endpoint does not persist the product.",
    }


@app.post("/products", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: boundaries checked against neighboring definitions.
- `UNVERIFIED — LOGIC`: tests, callers and behavior remain to be verified.
- `UNVERIFIED — LIVE BEHAVIOR`: no API endpoint was called.

## Required checks

Inspect request/response schema, authentication, direct callees, database query, tests, validation boundaries, failure mapping and secret/data exposure.
