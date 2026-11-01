# test_pinterest_client_marks_5xx_as_uncertain

- **Unique ID:** TEST-API-018
- **Definition type:** test function
- **Source:** `tests/test_api.py:344-375`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert exc.outcome_uncertain is True
assert exc.http_status == 500
```

## Evidence boundary
Read the complete test body in the current source range. Any monkeypatched database/provider dependency proves only behavior under the test double, not live external integration.

## Exact source

```python
def test_pinterest_client_marks_5xx_as_uncertain(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", "unit-test-token")

    class FakeResponse:
        status_code = 500

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.pinterest.httpx.Client", FakeClient)
    try:
        publish_image_pin(
            board_id="board-7", title="Title", description="Description",
            alt_text="Alt text", image_url=VALID_PRODUCT["image_url"],
            affiliate_url=VALID_PRODUCT["affiliate_url"],
        )
    except PinterestPublishError as exc:
        assert exc.outcome_uncertain is True
        assert exc.http_status == 500
    else:
        raise AssertionError("Expected PinterestPublishError")


```
