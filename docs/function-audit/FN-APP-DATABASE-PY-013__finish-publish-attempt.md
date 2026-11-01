# finish_publish_attempt — source-level review

- ID: `FN-APP-DATABASE-PY-013`; source `app/database.py:281-314`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Validates status is one of succeeded/failed/unknown; success requires a non-empty Pinterest Pin ID. Opens DB connection, updates publication status, Pin ID, HTTP status, error code, JSONB response metadata and updated timestamp by publication ID, then returns row as dict. If no row is returned, raises RuntimeError. Metadata is serialized with json.dumps when present.

## Callers and risks
Called after Pinterest publish attempts and by recovery paths. It does not independently enforce allowed prior-state transitions or verify that the supplied Pin belongs to the publication/account; route/state-machine callers provide policy. A direct caller could overwrite a previously terminal state if it has DB access. Never include access/refresh tokens in response_metadata. Tests use fake SQL harness plus disposable PostgreSQL intent; no live DB operation occurred.
