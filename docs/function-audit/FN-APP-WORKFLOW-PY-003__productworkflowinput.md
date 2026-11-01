# ProductWorkflowInput

- **Unique ID:** `FN-APP-WORKFLOW-PY-003`
- **Source:** `app/workflow.py:47-70`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This record isolates one definition. Review the source line by line, its direct callers, callees, tests and side effects before marking its behavior verified.

## Source excerpt

```python
class ProductWorkflowInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    affiliate_url: str = Field(min_length=8, max_length=4096)
    account_id: str = Field(min_length=1, max_length=200)
    board_name: str = Field(default="Modern Living Hub | Kitchen & Home Organization", min_length=1, max_length=100)
    board_description: str = Field(default="Kitchen organization, practical home finds, and home decor inspiration.", max_length=500)

    @field_validator("product_name", "product_details", "board_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("affiliate_url")
    @classmethod
    def valid_destination(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise ValueError("affiliate_url must be a valid absolute HTTP(S) URL without embedded credentials or surrounding whitespace")
        return value


```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
