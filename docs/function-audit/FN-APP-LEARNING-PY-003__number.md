# _number

- **Unique ID:** `FN-APP-LEARNING-PY-003`
- **Definition type:** `def`
- **Source:** `app/learning.py:33-48`
- **Source blob SHA:** `ea27a7ebf2fbdf58ba1452f4adaf7d56a197e9b9`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Numeric conversion helper for Pinterest analytics metrics. Verify missing/null/boolean/string handling, invalid numeric strings, integer/float precision and whether absent metrics are distinguished from true zero.

## Exact isolated source

```python
def _number(value: object) -> float:
    """Parse an explicitly returned metric; never turn missing/invalid data into fake zeroes."""
    if isinstance(value, dict):
        value = value.get("value", value.get("count"))
    if value is None or isinstance(value, bool):
        raise ValueError("Pinterest analytics metric is missing or invalid")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Pinterest analytics metric is missing or invalid") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("Pinterest analytics metric is outside the valid range")
    return number


@router.post("/run", dependencies=[Depends(_require_api_key)])
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current source blob.
- `VERIFIED — DEFINITION ISOLATION`: indentation-aware boundaries checked.
- `UNVERIFIED — LOGIC`: caller/test/runtime evidence not yet complete.
- `UNVERIFIED — LIVE BEHAVIOR`: no production execution occurred.

## Required checks

Trace every caller/callee, inspect relevant tests, validate boundary cases and exception behavior, and review security/data side effects. Do not call production services during this audit.
