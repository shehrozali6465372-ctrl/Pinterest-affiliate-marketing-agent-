# PinterestCredentialInput

- **Unique ID:** `FN-APP-MAIN-PY-007`
- **Definition type:** class/schema
- **Source:** `app/main.py:90-101`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Request schema for credential ingestion. Verify accepted account identity/token fields, secret-bearing fields, requiredness and validation. Ensure schema does not echo secrets in errors or serialization.

## Exact isolated source

```python
class PinterestCredentialInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    pinterest_user_id: str = Field(min_length=1, max_length=200)
    username: str = Field(default="", max_length=200)
    access_token: str = Field(min_length=1, max_length=10000)
    refresh_token: str = Field(default="", max_length=10000)
    token_type: str = Field(default="bearer", max_length=100)
    scope: str = Field(default="", max_length=2000)
    expires_at: str | None = None
    refresh_token_expires_at: str | None = None
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact class/schema source retrieved.
- `VERIFIED — DEFINITION ISOLATION`: adjacent class/function boundaries checked.
- `UNVERIFIED — VALIDATION CORRECTNESS`: actual accepted/rejected inputs and tests remain to be established.

## Required checks

Review Pydantic version/configuration, each field, defaults, validators, invalid payload tests, route binding, serialization and secret exposure.
