"""Pinterest API v5 image publishing with URL and Base64 media sources."""
from __future__ import annotations
import base64
import re

class PinterestPublishError(RuntimeError):
    """Error during publish, with explicit certainty about external side effects."""
    def __init__(self, message: str, *, outcome_uncertain: bool, http_status: int | None = None, error_code: str | None = None) -> None:
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain
        self.http_status = http_status
        self.error_code = error_code

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
