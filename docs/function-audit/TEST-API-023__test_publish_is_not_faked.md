# test_publish_is_not_faked

- **Unique ID:** TEST-API-023
- **Definition type:** test function
- **Source:** `tests/test_api.py:471-475`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 422
```

## Evidence boundary
Read the complete test body in the current source range. Test doubles and monkeypatches do not establish real Pinterest, Neon, Cloudflare or DeepSeek behavior. No publish-capable test was executed during this audit.

## Exact source

```python
def test_publish_is_not_faked(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "private-test-api-key")
    response = client.post("/publish", headers={"X-API-Key": "private-test-api-key"})
    assert response.status_code == 422


```
