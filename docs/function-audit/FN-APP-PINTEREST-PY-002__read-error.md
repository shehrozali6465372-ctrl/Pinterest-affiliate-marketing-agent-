# PinterestReadError

- **Unique ID:** FN-APP-PINTEREST-PY-002
- **Source:** app/pinterest.py (current definition retrieved; exact line coordinates pending final inventory)
- **Status:** VERIFIED — SOURCE RETRIEVED; line coordinates provisional

## Behavior
A dedicated RuntimeError subtype for sanitized failures from read-only Pinterest verification calls. It communicates a failure category to callers without embedding response bodies or credentials.

## Side effects
The exception class itself has no side effects. Read-only GET behavior belongs to list_board_pins_read_only and get_pin_read_only.

## Evidence boundary
Source retrieved from main. Caller handling and tests remain to be mapped. No live Pinterest request was made.
