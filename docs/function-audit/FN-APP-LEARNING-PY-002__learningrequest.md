# LearningRequest — source-level review

- ID: `FN-APP-LEARNING-PY-002`; source `app/learning.py:28-32`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic request model requires account_id with length 1–200; period_days defaults to 30 and is constrained 1–90. It does not accept arbitrary metric names; metric types are defined by module constants. Validation bounds API request scope but does not verify account ownership until credential lookup.

## Callers and tests
Consumed by `run_learning_loop`; tests construct the model with valid account IDs and default/custom periods. Invalid boundaries are handled by Pydantic/FastAPI 422.
