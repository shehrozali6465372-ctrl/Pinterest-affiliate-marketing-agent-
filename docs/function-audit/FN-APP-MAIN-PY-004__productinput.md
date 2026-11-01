# ProductInput

- **Unique ID:** `FN-APP-MAIN-PY-004`
- **Definition type:** class/schema
- **Source:** `app/main.py:62-89`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic request model for creating products. Explain every field, default, type constraint and validator; verify that affiliate URL validation is attached and product text limits align with Pinterest/provider constraints.

## Exact isolated source

```python
class ProductInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    image_url: HttpUrl
    # Keep affiliate URL as raw text so validation does not rewrite tracking parameters.
    affiliate_url: str = Field(min_length=8, max_length=4096)

    @field_validator("product_name", "product_details")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("affiliate_url")
    @classmethod
    def validate_affiliate_url_without_rewriting(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("affiliate_url must not contain leading or trailing whitespace")
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise ValueError("affiliate_url must be an absolute HTTP(S) URL")
        if parts.username or parts.password:
            raise ValueError("affiliate_url must not contain embedded credentials")
        return value
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact class/schema source retrieved.
- `VERIFIED — DEFINITION ISOLATION`: adjacent class/function boundaries checked.
- `UNVERIFIED — VALIDATION CORRECTNESS`: actual accepted/rejected inputs and tests remain to be established.

## Required checks

Review Pydantic version/configuration, each field, defaults, validators, invalid payload tests, route binding, serialization and secret exposure.
