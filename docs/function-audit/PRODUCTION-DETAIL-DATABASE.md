# Production definition review — app/database.py

Source baseline blob SHA: 7000abf6365c60b4543e353a72bbbcce2c49d2dd. All definitions below were inspected in the recorded source.

- DatabaseConfigurationError: dedicated RuntimeError for missing DATABASE_URL; does not wrap arbitrary SQL errors.
- get_pool(): lazy module-global psycopg ConnectionPool; refuses absent DB URL; uses dict_row, min_size=1, max_size=5, checkout check_connection and open=True. No explicit lock protects simultaneous first initialization; assess concurrent startup/request race.
- connection(): contextmanager yielding pool.connection(); transaction/lease behavior is delegated to psycopg_pool/psycopg.
- run_migrations(): opens one connection, creates schema_migrations, obtains transaction advisory lock 73219021, iterates numbered SQL files lexically, skips recorded versions, executes file text and inserts version. Correctness depends on transaction boundaries and pool connection context; migration files are trusted repository code.
- get_product_by_idempotency_key(): SELECT product row by key; returns dict or None.
- create_product(): INSERT supplied product metadata and optional idempotency key; returns row. Unique-index conflicts propagate.
- get_product(): SELECT one product by ID; returns dict or None.
- create_content_version(): advisory transaction lock keyed by product ID; computes MAX(version_number)+1; inserts generated fields and returns row. Lock serializes version allocation for same product if transaction semantics are honored.
- create_product_with_content_version(): inserts product then version 1 on same connection; returns both rows. Atomic rollback relies on transaction context. No explicit conflict recovery.
- get_content_version(): selects one version constrained by product ID and version ID.
- list_content_versions(): returns product versions ordered descending by version_number.
- begin_publish_attempt(): advisory lock keyed by content-version/board plus SELECT FOR UPDATE. Existing succeeded/pending/unknown rows block. Existing failed row is reset to pending and attempt_count incremented; absent row is inserted pending. Existing account_id is preserved with COALESCE. Caller must handle DB uniqueness/errors.
- finish_publish_attempt(): validates allowed terminal states; success requires Pin ID; updates outcome/status/metadata; JSON-serializes response metadata; missing row raises RuntimeError. It does not independently verify current state transition or affected account.
- get_publication(): reads limited operator-reconciliation fields by publication ID.
- reconcile_unknown_publication(): validates bounded nonblank evidence; permits only succeeded with Pin ID or failed without Pin ID; locks publication, requires current unknown state, updates status and appends operator evidence JSON. It does not contact Pinterest; trust boundary is caller's verification evidence.
- close_pool(): closes global pool and resets it to None; close exceptions propagate.

Cross-cutting review points:
1. Product idempotency key unique index is the final DB guard; initial read-before-write alone is not concurrency-safe.
2. begin_publish_attempt serializes by hashtext lock key; DB integration tests, not fake cursor tests, are needed to prove concurrent behavior.
3. finish_publish_attempt can update any existing publication ID to succeeded/failed/unknown without checking prior state; route callers enforce workflow policy. Consider DB-level transition constraints if multiple write paths exist.
4. reconcile_unknown_publication stores operator-supplied evidence as text; no schema for evidence type/source/verification timestamp is enforced.
5. Response metadata is JSONB and callers must ensure no token or sensitive payload is placed there.
6. No SQL was executed and no production DB was accessed in this review.