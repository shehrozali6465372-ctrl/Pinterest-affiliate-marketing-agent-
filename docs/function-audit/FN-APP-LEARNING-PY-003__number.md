# _number — source-level review

- ID: `FN-APP-LEARNING-PY-003`; source `app/learning.py:33-48`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Unwraps dict values from count/value fields as implemented; rejects None and booleans; converts supported numeric/string values to float; rejects conversion errors, non-finite values and negative metrics. Returns normalized float for valid non-negative metric. Boolean rejection is explicit because bool is an int subclass in Python.

## Callers and tests
Used when parsing Pinterest analytics summary/per-metric response shapes before snapshot persistence and aggregate calculations. `tests/test_learning.py` covers valid numbers, invalid/missing/negative/non-finite inputs and metric shape handling. No live analytics response was parsed.
