# learning_loop_unavailable — source-level review

- ID: `FN-APP-MAIN-PY-030`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Explicit fallback route handler returns an unavailable response when Learning Loop router is not mounted/available. It does not query analytics, write snapshots, train a model or invoke providers. It should not be confused with app.learning.run_learning_loop, which is the actual analytics ingestion handler.

## Callers and tests
Compatibility/route fallback only. No learning operation was run during audit.
