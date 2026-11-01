# strip_required_text

- **Unique ID:** `FN-APP-MAIN-PY-005`
- **Definition:** `def`
- **Source:** `app/main.py:71-78`
- **Source blob SHA:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic text validator that normalizes/rejects required text. Verify None/non-string handling, whitespace stripping, empty values and preservation of meaningful Unicode.

## Exact isolated source

```python
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("affiliate_url")
    @classmethod
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: exact source blob fetched.
- `VERIFIED — DEFINITION ISOLATION`: one definition body isolated.
- `UNVERIFIED — LOGIC`: tests and all call sites remain to be inspected.

## Required checks

Trace route dependencies and model validators, test accepted/rejected values, verify status codes, authentication behavior, data redaction and exception handling.
