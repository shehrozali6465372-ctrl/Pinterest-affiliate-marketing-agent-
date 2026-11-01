# get_pool — source-level review

- **ID:** `FN-APP-DATABASE-PY-002`
- **Source:** `app/database.py:23-42`
- **Source blob:** `7000abf6365c60b4543e353a72bbbcce2c49d2dd`
- **Baseline:** `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Source review:** COMPLETE
- **Runtime verification:** NOT RUN

## Statement-level behavior

1. Declares `_pool` global so the pool instance is shared by module callers.
2. If `settings.database_url` is falsy, raises `DatabaseConfigurationError`; no connection attempt occurs.
3. If `_pool is None`, constructs `ConnectionPool` with the configured DSN, `dict_row` row factory, minimum one and maximum five connections, checkout health check, and `open=True`.
4. The newly created pool is assigned to the global and returned.
5. If a pool already exists, the same instance is returned without revalidating the DSN or reopening it.

## Callers and invariants

`connection()` obtains a connection lease from this pool. Database helpers use that context for product/content/publication/analytics/credential queries; `close_pool()` closes and resets the module global. The configured maximum of five bounds pool size per process, not across multiple Render instances.

## Risks and tests

The check-then-create sequence has no explicit lock, so concurrent first calls can race and construct more than one pool; the overwritten pool may leak. The pool's checkout check is intended to discard stale idle connections, but only a real psycopg_pool/PostgreSQL integration test can prove recovery. Fake pool tests validate mocked lifecycle only. The opt-in recovery integration test terminates a backend session and must run only against disposable PostgreSQL.

## Finding

**P2 — concurrent lazy initialization is not serialized.** Consider initializing the pool during a controlled lifespan/startup path or protecting initialization with a lock. Verify close/reopen behavior and multi-worker process limits. No database connection was opened in this audit.
