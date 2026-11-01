# PinterestPublishError.__init__

- **Unique ID:** FN-APP-PINTEREST-PY-001A
- **Definition type:** method
- **Source:** `app/pinterest.py:11-15`
- **Source blob SHA:** `6ccc51b2cf8a289f6989e872179a0014cfe6f372`
- **Status:** VERIFIED — SOURCE RETRIEVED

## Exact source

```python
def __init__(self, message: str, *, outcome_uncertain: bool, http_status: int | None = None, error_code: str | None = None) -> None:
    super().__init__(message)
    self.outcome_uncertain = outcome_uncertain
    self.http_status = http_status
    self.error_code = error_code
```

## Behavior
Initializes the RuntimeError message and three structured fields. `outcome_uncertain` is mandatory and keyword-only; HTTP status and error code are optional. The method does not retry. Its certainty flag is consumed by the workflow to decide whether an attempted Pinterest write can safely be retried or must be marked unknown.

## Evidence boundary
Definition and caller behavior statically inspected. Unit tests cover selected 5xx uncertainty behavior; no real Pinterest write was attempted.
