# test_generated_data_url_uses_pinterest_base64_source

- **Unique ID:** TEST-IMAGE-BASE64-001
- **Definition type:** test function
- **Source:** `tests/test_image_base64.py:6-16`
- **Production target:** `app.pinterest.image_media_source`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Builds a PNG-like byte payload larger than the production minimum, Base64-encodes it, and passes a data URL to `image_media_source`. Assertions require source_type=image_base64, correct MIME type, preserved encoded data, is_standard=true and absence of a URL field.

## What it proves
When this test passes, the helper's Base64 branch produces the expected Pinterest media_source structure for the supplied test input.

## What it does not prove
It does not validate a real image decoder, Pinterest acceptance, image dimensions, upload or Pin publication. The bytes after the PNG signature are synthetic.
