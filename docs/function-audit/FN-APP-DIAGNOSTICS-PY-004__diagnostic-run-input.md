# DiagnosticRunInput

- **Unique ID:** `FN-APP-DIAGNOSTICS-PY-004`
- **Source:** `app/diagnostics.py:137-143`
- **Source blob SHA:** `8a1f7b8092c99f9102565c721967d0fa2b50609a`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Pydantic request schema for selecting diagnostic checks. Verify defaults, allowed option names, strictness and whether callers can request any potentially side-effecting check.

## Exact isolated source

```python
class DiagnosticRunInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    product_name: str = Field(default="Kitchen spice rack organizer", min_length=1, max_length=300)
    product_details: str = Field(default="A practical organizer for spices in a home kitchen.", min_length=1, max_length=1000)


@router.post("/run", dependencies=[Depends(_require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from exact source blob.
- `VERIFIED — LINE RANGE`: isolated against neighboring definitions.
- `UNVERIFIED — LOGIC`: call sites and tests remain to be checked.
