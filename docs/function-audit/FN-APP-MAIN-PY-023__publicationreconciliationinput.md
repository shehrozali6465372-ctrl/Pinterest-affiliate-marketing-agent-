# PublicationReconciliationInput

- **Unique ID:** `FN-APP-MAIN-PY-023`
- **Definition:** `class`
- **Source:** `app/main.py:520-534`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic schema for reconciling uncertain Pin publication. Inspect every evidence field and validator, required evidence strength, accepted Pin/account/board IDs and prevention of unsupported state changes.

## Exact isolated source

```python
class PublicationReconciliationInput(BaseModel):
    outcome: str = Field(pattern=r"^(succeeded|failed)$")
    pinterest_pin_id: str | None = Field(default=None, min_length=1, max_length=200)
    operator_evidence: str = Field(min_length=12, max_length=2000)

    @field_validator("operator_evidence")
    @classmethod
    def evidence_must_be_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("operator_evidence must not be blank")
        return value


@app.get("/publications/{publication_id}", dependencies=[Depends(require_configured_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: one definition body isolated.
- `UNVERIFIED — LOGIC`: tests and all call sites remain to be inspected.

## Required checks

Trace route dependencies and model validators, test accepted/rejected values, verify status codes, authentication behavior, data redaction and exception handling.
