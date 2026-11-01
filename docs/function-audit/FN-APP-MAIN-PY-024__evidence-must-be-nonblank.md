# evidence_must_be_nonblank — source-level review

- ID: `FN-APP-MAIN-PY-024`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic validator strips whitespace and rejects evidence that becomes empty; returns normalized evidence string. It enforces presence but not truthfulness, source provenance, timestamp, completeness of Pinterest pagination or operator identity.

## Callers and trust boundary
Attached to reconciliation evidence field. Database helper stores free-form evidence. The API must only accept evidence after operator has verified Pin state; no reconciliation was performed.
