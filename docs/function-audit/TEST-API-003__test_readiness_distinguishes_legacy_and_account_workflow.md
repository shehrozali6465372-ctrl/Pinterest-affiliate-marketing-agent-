# test_readiness_distinguishes_legacy_and_account_workflow

- **Unique ID:** TEST-API-003
- **Definition type:** test function
- **Source:** `tests/test_api.py:46-61`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert body["pinterest_configured"] is False
assert body["pinterest_legacy_direct_configured"] is False
assert body["pinterest_account_workflow_configured"] is True
assert body["pinterest_token_encryption_key_valid"] is True
assert body["pinterest_credential_ingest_configured"] is True
assert "account connection" in body["note"]
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_readiness_distinguishes_legacy_and_account_workflow(monkeypatch):
    monkeypatch.setattr(settings, "pinterest_access_token", None)
    monkeypatch.setattr(settings, "pinterest_board_id", None)
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(settings, "pinterest_token_encryption_key", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setattr(settings, "pinterest_credential_ingest_key", "configured-ingest-key")

    body = client.get("/readiness").json()

    assert body["pinterest_configured"] is False
    assert body["pinterest_legacy_direct_configured"] is False
    assert body["pinterest_account_workflow_configured"] is True
    assert body["pinterest_token_encryption_key_valid"] is True
    assert body["pinterest_credential_ingest_configured"] is True
    assert "account connection" in body["note"]


```
