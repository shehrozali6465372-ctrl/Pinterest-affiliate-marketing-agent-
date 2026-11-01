# image_media_source — source-level review

- ID: `FN-APP-PINTEREST-PY-003`; source `app/pinterest.py:17-33`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Behavior
If input begins with a data URL, splits header and Base64 payload, validates supported image MIME/format, strict-decodes Base64, rejects malformed/unsupported/small content and returns Pinterest `image_base64` media_source with MIME and encoded data. For non-data input it preserves legacy public URL path as `image_url` source. It does not upload to a hosting service.

## Callers and tests
Used by `publish_image_pin` and diagnostics to convert generated data URL to Pinterest media source. `test_image_base64.py` covers valid/invalid data URLs and legacy URL behavior. No Pinterest POST was made. Remote URL reachability/content is not verified by this helper.
