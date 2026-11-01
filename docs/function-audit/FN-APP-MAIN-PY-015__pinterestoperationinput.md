# PinterestOperationInput — source-level review

- ID: `FN-APP-MAIN-PY-015`; source `app/main.py`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN.

## Behavior
Pydantic schema requires account_id 1–200 and operation 1–50; payload defaults to empty dict with arbitrary object values. It does not schema-validate operation-specific fields; handler performs limited required-field checks after allowlist lookup.

## Callers and security
Consumed by pinterest_account_operation. Service key is required there. Allowlisted create_board/create_pin operations perform real Pinterest writes outside publication ledger. Generic dict shape and shallow validation increase caller responsibility. No operation was invoked.
