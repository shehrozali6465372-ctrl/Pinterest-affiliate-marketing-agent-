# _log_workflow_failure

- **Unique ID:** `FN-APP-WORKFLOW-PY-002`
- **Source:** `app/workflow.py:32-46`
- **Blob SHA:** `66ba65415cb69b5d8c9ac64f920690ebe616a0ab`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Logic analysis

Structured workflow failure logger. It records a stage, request correlation ID, sanitized error metadata and status while intending not to expose credentials or product/provider payloads. Verify redaction against every exception type and ensure logging itself cannot mask the original failure.

## Exact isolated source

```python
def _log_workflow_failure(stage: str, exc: Exception, request_id: str, *, http_status: int | None = None) -> None:
    """Log safe failure classification without exception messages or request data."""
    diagnostic = getattr(exc, "diag", None)
    sqlstate = getattr(exc, "sqlstate", None) or "unknown"
    table_name = getattr(diagnostic, "table_name", None) or "unknown"
    column_name = getattr(diagnostic, "column_name", None) or "unknown"
    constraint_name = getattr(diagnostic, "constraint_name", None) or "unknown"
    logger.error(
        "workflow stage=%s outcome=failed request_id=%s exception_type=%s http_status=%s "
        "sqlstate=%s table=%s column=%s constraint=%s",
        stage, request_id, type(exc).__name__, http_status if http_status is not None else "unknown",
        sqlstate, table_name, column_name, constraint_name,
    )
```

## Evidence tags

- `VERIFIED — SOURCE PRESENT`: confirmed from the recorded GitHub blob.
- `VERIFIED — DEFINITION ISOLATION`: one definition only; nested definitions are separate records.
- `UNVERIFIED — LOGIC CORRECTNESS`: callers, tests and security edge cases still need review.
- `UNVERIFIED — PRODUCTION BEHAVIOR`: no live calls were made.

## Next verification

Inspect all call sites, related Pydantic schemas and route dependencies; map tests for valid/invalid inputs, missing secrets, HTTP transport failures, non-JSON responses, timeouts, retries, and secret redaction. Do not invoke publishing endpoints.
