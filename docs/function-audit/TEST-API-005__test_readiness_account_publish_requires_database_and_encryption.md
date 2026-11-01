# test_readiness_account_publish_requires_database_and_encryption

- **Unique ID:** TEST-API-005
- **Definition type:** test function
- **Source:** `tests/test_api.py:75-85`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert body["pinterest_account_workflow_configured"] is False
assert body["pinterest_token_encryption_key_valid"] is False
assert body["pinterest_credential_ingest_configured"] is True
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_readiness_account_publish_requires_database_and_encryption(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", None)
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "configured-ingest-key")

    body = client.get("/readiness").json()

    assert body["pinterest_account_workflow_configured"] is False
    assert body["pinterest_token_encryption_key_valid"] is False
    assert body["pinterest_credential_ingest_configured"] is True


```
