# ImageGenerationError

- **Unique ID:** `FN-APP-MEDIA-GENERATION-PY-001`
- **Source:** `app/media_generation.py:17-19`
- **Source blob SHA:** `e4a62e8ca628ee906bc59915810edc20e3c8f8e7`
- **Snapshot:** `main source snapshot 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Domain exception for image generation or upload failures. Verify callers map it correctly and messages are sanitized.

## Exact isolated source

```python
class ImageGenerationError(RuntimeError):
    """Raised when image generation fails or returns unusable data."""
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION RANGE`: single definition isolated.
- `UNVERIFIED — LOGIC CORRECTNESS`: tests and call graph still require verification.
- `UNVERIFIED — LIVE BEHAVIOR`: no external provider call was executed.

## Required checks

Review all call sites, test cases, input boundaries, exception behavior, provider contracts, retry safety and secret redaction.
