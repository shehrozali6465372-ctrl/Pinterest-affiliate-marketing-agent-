# test_invalid_data_url_is_rejected_before_request

- **Unique ID:** TEST-IMAGE-BASE64-003
- **Definition type:** test function
- **Source:** `tests/test_image_base64.py:28-38`
- **Production target:** `app.pinterest.image_media_source`
- **Status:** VERIFIED — ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Test behavior
Passes malformed Base64 characters in a PNG data URL and expects PinterestPublishError. It asserts error_code=invalid_image_data and outcome_uncertain=false; otherwise it raises AssertionError.

## What it proves
Malformed input is rejected locally with a determinate no-write classification for this case.

## What it does not prove
It does not exercise the HTTP client or Pinterest. The test's “before request” property follows from testing the pure media-source helper; there is no request mock assertion in this function.
