# pinterest_account_operation — source-level review

- ID: `FN-APP-MAIN-PY-017`; source `app/main.py:378-423`; baseline `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`.
- Source review: COMPLETE. Runtime verification: NOT RUN. This route includes real provider writes.

## Control flow
1. Requires configured service key and constant-time comparison of `X-Credential-Ingest-Key`.
2. Loads decrypted access token for account ID; missing/disconnected account returns 404.
3. Constructs Pinterest API base URL and Bearer/JSON headers.
4. Allowlist maps account to GET /user_account, boards to GET /boards?page_size=100, create_board to POST /boards, and create_pin to POST /pins. The create_pin payload uses image_url and destination_url supplied by caller.
5. Disconnect branch updates local credential status to revoked and returns disconnected=true; it does not call provider OAuth revocation.
6. Rejects unsupported operation and checks required board name / Pin fields.
7. Sends the mapped HTTP request with 45-second total/10-second connect timeout; transport errors map 502; non-success upstream status is normalized; success returns provider JSON.

## Callers, tests and security
This is a service-key-protected generic operation surface. Its create_board/create_pin operations bypass the publication ledger, idempotency key, unknown-outcome tracking and operator reconciliation. The response returns provider JSON without a field-level allowlist. The boards GET is limited to one page.

No live request or write was executed. Treat create_board/create_pin as side-effecting endpoints requiring explicit approval. Prefer removing write operations or routing them through the same durable publication state machine.
