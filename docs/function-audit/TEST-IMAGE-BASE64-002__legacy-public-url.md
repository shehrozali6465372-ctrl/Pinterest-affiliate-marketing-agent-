# test_legacy_public_url_keeps_image_url_source

- **Unique ID:** TEST-IMAGE-BASE64-002
- **Definition type:** test function
- **Source:** `tests/test_image_base64.py:18-26`
- **Production target:** `app.pinterest.image_media_source`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Passes a public HTTPS image URL and asserts the helper returns the legacy Pinterest image_url source with the original URL and is_standard=true.

## What it proves
The legacy URL branch preserves the supplied string in the media-source object.

## What it does not prove
No HTTP fetch, URL accessibility check, image validation or Pinterest request occurs. The example domain is not evidence of a reachable image.
