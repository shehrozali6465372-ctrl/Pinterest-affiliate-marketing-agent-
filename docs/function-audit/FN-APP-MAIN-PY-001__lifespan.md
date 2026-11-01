# lifespan — source-level review

- ID: `FN-APP-MAIN-PY-001`; source `app/main.py:20-27`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Async context manager yields control to FastAPI startup/lifespan. In finally after application shutdown, imports close_pool and calls it. Any exception during import/close is swallowed. This allows shutdown to proceed but can hide pool-close failures.

## Callers and tests
Registered as FastAPI app lifespan. `tests/test_diagnostics.py::test_app_lifespan_closes_database_pool` monkeypatches close_pool and asserts it is called. Test does not exercise real in-flight connection shutdown or close failure observability.
