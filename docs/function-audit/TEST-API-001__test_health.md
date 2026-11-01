# test_health

- **Unique ID:** TEST-API-001
- **Definition type:** test function
- **Source:** `tests/test_api.py:25-29`
- **Status:** VERIFIED — SOURCE RETRIEVED AND ASSERTIONS MAPPED; NOT EXECUTED IN THIS AUDIT

## Purpose and assertions
This test exercises the named API/application behavior. Its explicit assertions are:

```python
assert response.status_code == 200
assert response.json()["status"] == "ok"
```

## Evidence boundary
Read the complete test body in the current source range. Where the test monkeypatches database/provider dependencies, it proves only the local route behavior under those test doubles; it does not prove production DB/provider behavior.

## Exact source

```python
def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


```
