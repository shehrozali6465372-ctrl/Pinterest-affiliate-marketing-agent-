# database_diagnostic — source-level review

- ID: `FN-APP-DIAGNOSTICS-PY-002`; source `app/diagnostics.py:22-47`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime DB verification: NOT RUN.

## Behavior
Fail-closed router auth runs before handler. Handler obtains DB connection and executes read-only `SELECT 1 AS connection_test, current_database() AS database_name`; validates expected result; returns connected status, database name, query label and explicit no-mutation/no-Pinterest/no-generation flags. Any unexpected exception becomes sanitized HTTP 503. It does not migrate schema or write rows.

## Tests and limits
Diagnostics tests mock connection and exercise successful/failing DB behavior. This source-level path is read-only, but a test against production would still reveal database name; no production query was run.
