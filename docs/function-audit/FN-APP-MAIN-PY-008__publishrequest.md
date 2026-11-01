# PublishRequest

- **Unique ID:** `FN-APP-MAIN-PY-008`
- **Definition type:** class/schema
- **Source:** `app/main.py:102-106`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Request model for publishing a selected product/content version. Verify required IDs, board/account selection, idempotency controls and that client-supplied content cannot bypass approved persisted content rules.

## Exact isolated source

```python
class PublishRequest(BaseModel):
    product_id: int = Field(gt=0)
    content_version_id: int = Field(gt=0)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact class/schema source retrieved.
- `VERIFIED — DEFINITION ISOLATION`: adjacent class/function boundaries checked.
- `UNVERIFIED — VALIDATION CORRECTNESS`: actual accepted/rejected inputs and tests remain to be established.

## Required checks

Review Pydantic version/configuration, each field, defaults, validators, invalid payload tests, route binding, serialization and secret exposure.
