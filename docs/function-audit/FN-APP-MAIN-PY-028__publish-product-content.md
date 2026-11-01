# publish_product_content

- **Unique ID:** `FN-APP-MAIN-PY-028`
- **Source:** `app/main.py:627-680`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Publishing orchestration route for an already-created product/content version. It resolves stored content, credential, media and board; calls Pinterest publish helper; persists publication outcome. It can create a real Pin. It was not executed in this audit.

## Exact isolated source

```python
def publish_product_content(product_id: int, content_version_id: int) -> dict[str, object]:
    if product_id <= 0 or content_version_id <= 0:
        raise HTTPException(status_code=422, detail="product_id and content_version_id must be positive integers")
    if not settings.pinterest_access_token or not settings.pinterest_board_id:
        raise HTTPException(status_code=503, detail="Pinterest access token and board ID must be configured before publishing.")

    from app.database import begin_publish_attempt, finish_publish_attempt, get_content_version, get_product as fetch_product
    try:
        product = fetch_product(product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        content = get_content_version(product_id, content_version_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Content version not found")

        attempt = begin_publish_attempt(product_id=product_id, content_version_id=content_version_id, board_id=settings.pinterest_board_id)
        if attempt.get("blocked"):
            if attempt["status"] == "succeeded":
                return {"published": True, "already_published": True, "pin_id": attempt["pinterest_pin_id"], "publication_id": attempt["id"]}
            raise HTTPException(status_code=409, detail="Previous publish attempt is pending or uncertain. Check Pinterest before retrying.")

        try:
            actual = publish_image_pin(
                board_id=settings.pinterest_board_id,
                title=content["title"],
                description=content["description"],
                alt_text=content["alt_text"],
                image_url=product["image_url"],
                affiliate_url=product["affiliate_url"],
            )
        except PinterestPublishError as exc:
            outcome = "unknown" if exc.outcome_uncertain else "failed"
            finish_publish_attempt(attempt["id"], status=outcome, http_status=exc.http_status, error_code=exc.error_code, response_metadata={})
            if exc.outcome_uncertain:
                raise HTTPException(status_code=502, detail="Pinterest publish outcome is uncertain. Automatic retry is blocked; verify the board before retrying.") from exc
            raise HTTPException(status_code=502, detail="Pinterest rejected the request. No successful Pin creation was confirmed.") from exc

        saved = finish_publish_attempt(
            attempt["id"],
            status="succeeded",
            pinterest_pin_id=str(actual["pin_id"]),
            http_status=int(actual["http_status"]),
            response_metadata=actual["metadata"],
        )
        return {"published": True, "already_published": False, "pin_id": saved["pinterest_pin_id"], "publication_id": saved["id"], "http_status": saved["http_status"]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Publish request could not be fully recorded. Inspect publication record and Pinterest board before retrying.") from exc


@app.post("/publish", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob retrieved.
- `VERIFIED — LINE RANGE`: isolated by Python definition boundary.
- `UNVERIFIED — LOGIC`: complete call graph, edge cases and tests not yet proven.
- `UNVERIFIED — LIVE BEHAVIOR`: no live endpoint or Pinterest operation invoked.

## Required checks

Trace all callees and route dependencies; inspect associated tests; verify request validation, authorization, idempotency, DB transaction outcomes, Pinterest response parsing, uncertainty handling and affiliate-link preservation. Any publish-capable call must remain unexecuted in this read-only task.
