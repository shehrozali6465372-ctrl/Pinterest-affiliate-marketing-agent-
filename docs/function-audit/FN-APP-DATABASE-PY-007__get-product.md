# get_product — source-level review

- ID: `FN-APP-DATABASE-PY-007`; source `app/database.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Performs parameterized SELECT for one product ID; returns dict row or None. It does not validate positive ID, authorize tenant/account ownership or fetch related content; route layer validates ID and handles not-found.

## Callers and tests
Used by product read, content generation/history and publish routes. API tests stub result and cover missing product. Product rows contain caller-supplied details and affiliate URL; do not treat them as independently verified facts.
