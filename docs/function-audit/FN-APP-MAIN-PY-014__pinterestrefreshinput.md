# PinterestRefreshInput

- **Unique ID:** `FN-APP-MAIN-PY-014`
- **Definition type:** class/schema
- **Source:** `app/main.py:238-243`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Request schema for token refresh. Verify account ID requirements, any optional refresh token acceptance, and whether server uses the encrypted stored refresh credential rather than trusting arbitrary client token material.

## Exact isolated source

```python
class PinterestRefreshInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=500)
    client_secret: str = Field(min_length=1, max_length=2000)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact class/schema source retrieved.
- `VERIFIED — DEFINITION ISOLATION`: adjacent class/function boundaries checked.
- `UNVERIFIED — VALIDATION CORRECTNESS`: actual accepted/rejected inputs and tests remain to be established.

## Required checks

Review Pydantic version/configuration, each field, defaults, validators, invalid payload tests, route binding, serialization and secret exposure.
