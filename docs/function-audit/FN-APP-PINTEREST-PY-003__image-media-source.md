# image_media_source

- **Unique ID:** `FN-APP-PINTEREST-PY-003`
- **Source:** `app/pinterest.py:17-33`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Converts an image reference into Pinterest's media_source shape. Verify data URL/base64 parsing, remote image URL handling, MIME assumptions and Pinterest API media_source contract. Invalid data URLs must fail before a publish request.

## Exact isolated source

```python
def image_media_source(image_url: str) -> dict[str, object]:
    """Use image_base64 for a data URL, otherwise preserve legacy public image URLs."""
    if image_url.startswith("data:"):
        match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", image_url)
        if not match:
            raise PinterestPublishError("Generated image data URL is malformed; no Pinterest request was sent.", outcome_uncertain=False, error_code="invalid_image_data")
    else:
        return {"source_type": "image_url", "url": image_url, "is_standard": True}
    mime, encoded = match.groups()
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise PinterestPublishError("Generated image data is invalid; no Pinterest request was sent.", outcome_uncertain=False, error_code="invalid_image_data") from exc
    if len(raw) < 1024:
        raise PinterestPublishError("Generated image data is unexpectedly small; no Pinterest request was sent.", outcome_uncertain=False, error_code="image_data_too_small")
    return {"source_type": "image_base64", "content_type": mime, "data": encoded, "is_standard": True}
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from the exact source blob above.
- `VERIFIED — DEFINITION ISOLATION`: one definition and its complete body only.
- `UNVERIFIED — LOGIC CORRECTNESS`: call graph, tests and edge cases remain to be proven.
- `UNVERIFIED — LIVE PINTEREST BEHAVIOR`: no provider call was executed.

## Remaining checks

Trace every caller, review tests, compare request/response with Pinterest API contract, inspect all exceptions and timeout cases, and verify no duplicate Pin can result from retries. Do not call this function during this audit.
