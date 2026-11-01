# generate_product_content

- **Unique ID:** `FN-APP-MAIN-PY-021`
- **Source:** `app/main.py:468-502`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Creates a new generated content version for an existing product. Verify it loads product details, calls DeepSeek, handles model errors, persists a version and does not publish a Pin as a side effect.

## Exact isolated source

```python
def generate_product_content(product_id: int) -> dict[str, object]:
    if product_id <= 0:
        raise HTTPException(status_code=422, detail="product_id must be a positive integer")
    try:
        from app.database import create_content_version, get_product as fetch_product
        product = fetch_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        generated, model_id = generate_pin_content(
            product_name=product["product_name"],
            product_details=product["product_details"],
            image_url=product["image_url"],
        )
        row = create_content_version(
            product_id=product_id,
            provider="deepseek",
            model_id=model_id,
            prompt_version=PROMPT_VERSION,
            pin_idea=generated.pin_idea,
            title=generated.title,
            description=generated.description,
            alt_text=generated.alt_text,
        )
        return _serialize_row(row)
    except HTTPException:
        raise
    except ContentGenerationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Content generation or persistence failed. Check database and provider configuration.") from exc


@app.get("/products/{product_id}/content", dependencies=[Depends(require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current main source.
- `VERIFIED — LINE RANGE`: isolated using neighboring definition boundaries.
- `UNVERIFIED — LOGIC`: callers, tests and edge cases still require review.
- `UNVERIFIED — LIVE BEHAVIOR`: no endpoint/provider action was executed.

## Required checks

Trace direct callees and authorization dependencies; inspect all matching tests; verify database persistence, validation, exception handling, idempotency and no unintended Pinterest side effects.
