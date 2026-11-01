# Production definition review — app/workflow.py

Source baseline blob SHA: 66ba65415cb69b5d8c9ac64f920690ebe616a0ab.

- _require_api_key(): router dependency enforcing configured app API key with constant-time compare.
- _log_workflow_failure(stage, exc, request_id, http_status): logs safe classification (exception type, SQLSTATE and schema diagnostic identifiers); deliberately avoids exception message/request content.
- ProductWorkflowInput: validates nonblank product name/details/board name; caps lengths; validates affiliate URL as absolute HTTP(S), host present, no embedded credentials or surrounding whitespace. It does not fetch product details or validate affiliate-program ownership.
- nonblank(): strips surrounding whitespace and rejects empty values.
- valid_destination(): parses URL and preserves original input string after validation.
- _pinterest_request(method, path, token, body): issues authenticated Pinterest request with 45s total/10s connect timeout; parses JSON if body exists; maps transport/JSON errors to 502; maps provider 5xx to 502 and other non-success to provider status; returns status and parsed payload. It is generic and does not distinguish safe GET from uncertain POST outcomes.
- _ensure_board(token, name, description): GETs first 100 boards, finds case-insensitive exact name, otherwise POSTs create board and requires returned ID. It does not follow bookmarks; it can create a duplicate if target board is beyond first page. Board creation is a side effect.
- publish_product_end_to_end(): full real publishing state machine documented separately in FN-APP-WORKFLOW-PY-008 and PRODUCTION-CALL-GRAPH-AND-RISK-REVIEW.md. It validates idempotency, checks credential/account, resolves board, generates image/content, atomically persists product/content, reserves publication attempt, posts Pin and records confirmed Pin ID or unknown state.

Cross-cutting risks:
1. Generic _pinterest_request maps transport errors to 502 without exposing a structured uncertain-outcome flag; publish caller conservatively marks 5xx as unknown but relies on status mapping.
2. _ensure_board is not paginated and can create a board before the rest of the workflow succeeds.
3. Idempotency key is first read before external generation and inserted only after generation. DB unique index is essential for concurrent requests; caller currently needs to handle insert conflict safely.
4. Request correlation ID is sanitized but caller-supplied IDs may still be reused across requests; uniqueness is not guaranteed.
5. Product details are caller-provided facts; no independent source validation.
6. No endpoint was invoked and no Pinterest write occurred in this review.