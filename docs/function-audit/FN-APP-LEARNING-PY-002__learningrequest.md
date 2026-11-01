# LearningRequest

- **Unique ID:** `FN-APP-LEARNING-PY-002`
- **Definition type:** `class`
- **Source:** `app/learning.py:28-32`
- **Source blob SHA:** `ea27a7ebf2fbdf58ba1452f4adaf7d56a197e9b9`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic explanation

Request schema for analytics/learning execution. Verify account ID, requested metric list, date/time filters and metric allowlist; reject arbitrary fields that could cause broad data collection.

## Exact isolated source

```python
class LearningRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    period_days: int = Field(default=30, ge=1, le=90)
```

## Verification tags

- `VERIFIED — SOURCE PRESENT`: fetched from current source blob.
- `VERIFIED — DEFINITION ISOLATION`: indentation-aware boundaries checked.
- `UNVERIFIED — LOGIC`: caller/test/runtime evidence not yet complete.
- `UNVERIFIED — LIVE BEHAVIOR`: no production execution occurred.

## Required checks

Trace every caller/callee, inspect relevant tests, validate boundary cases and exception behavior, and review security/data side effects. Do not call production services during this audit.
