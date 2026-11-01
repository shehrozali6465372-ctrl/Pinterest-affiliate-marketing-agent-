# PinterestOperationInput

- **Unique ID:** `FN-APP-MAIN-PY-015`
- **Definition type:** class/schema
- **Source:** `app/main.py:244-250`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Schema constraining account-level Pinterest operations. Verify enum/allowlist of operations and that mutating actions are clearly separated from read-only operations.

## Exact isolated source

```python
class PinterestOperationInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    operation: str = Field(min_length=1, max_length=50)
    payload: dict[str, object] = Field(default_factory=dict)


@app.post("/integrations/pinterest/refresh")
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact class/schema source retrieved.
- `VERIFIED — DEFINITION ISOLATION`: adjacent class/function boundaries checked.
- `UNVERIFIED — VALIDATION CORRECTNESS`: actual accepted/rejected inputs and tests remain to be established.

## Required checks

Review Pydantic version/configuration, each field, defaults, validators, invalid payload tests, route binding, serialization and secret exposure.
