# test_readiness_does_not_expose_secrets

- **Unique ID:** TEST-API-002
- **Definition type:** test function
- **Source:** `tests/test_api.py:31-44`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert "database_configured" in body
assert "pinterest_configured" in body
assert "pinterest_legacy_direct_configured" in body
assert "pinterest_account_workflow_configured" in body
assert "pinterest_token_encryption_key_valid" in body
assert "pinterest_credential_ingest_configured" in body
assert "image_generation_configured" in body
assert "llm_configured" in body
assert "access_token" not in str(body).lower()
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_readiness_does_not_expose_secrets():
    response = client.get("/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "database_configured" in body
    assert "pinterest_configured" in body
    assert "pinterest_legacy_direct_configured" in body
    assert "pinterest_account_workflow_configured" in body
    assert "pinterest_token_encryption_key_valid" in body
    assert "pinterest_credential_ingest_configured" in body
    assert "image_generation_configured" in body
    assert "llm_configured" in body
    assert "access_token" not in str(body).lower()


```
