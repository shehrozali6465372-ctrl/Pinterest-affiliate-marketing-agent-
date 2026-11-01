# _pinterest_request — source-level review

- ID: `FN-APP-WORKFLOW-PY-006`; source `app/workflow.py:69-81`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime Pinterest verification: NOT RUN.

## Behavior
Builds configured API URL + path, sends request with Bearer token/JSON headers and optional JSON body using 45s total/10s connect timeout. Parses JSON when response has content; empty body becomes {}. HTTP/JSON/transport errors are converted to HTTP 502 with generic retry warning. Non-success HTTP responses map 4xx status directly and 5xx to 502. Successful response returns status and parsed payload.

## Callers and risks
Used for GET /user_account, GET /boards and POST /boards /pins. It does not expose a structured outcome_uncertain flag distinguishing GET from non-idempotent POST. Caller conservatively maps 5xx/502 to unknown for Pin publish; board creation ambiguity is not durably tracked. No request was sent.
