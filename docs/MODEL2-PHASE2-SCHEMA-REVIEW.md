# Model 2 — Phase 2 Schema Review

**Status:** IN PROGRESS — owner model selected; revised schema proposal awaits executable verification and final schema approval.
**Date:** 2026-11-08
**Baseline:** Agent commit `785efd99849627062c1fff8504d21ca91abfee8e`, isolated branch `feat/model2-open-source-reuse`.
**Reviewed artifact:** draft `migrations/013_model2_account_niche_registry.sql`.
**Safety:** source-only review. No migration was applied to any database.

## 1. Executive decision

Migration 013 has been revised after the owner selected the single-operator model. It now proposes six additive tables, credential linkage, explicit immutable publication attribution, raw-analytics source lineage with deferred count validation, bounded JSONB contracts and restrictive historical FKs. It is **not ready to accept or apply** until SQL execution and the remaining PostgreSQL invariants are verified.

Do not run migration 013 in production. Do not implement repositories/APIs against this draft until Phase 2 verification and approval are complete.

## 2. What is already correct in the draft

- Migration is additive and does not backfill or mutate existing credentials, publications, schedules, products or raw analytics.
- Six tables separate niche taxonomy, account profile, account–niche mapping, immutable publication attribution, derived learning snapshots and immutable raw-analytics source evidence.
- Niche slug has a lowercase/hyphenated format check and uniqueness.
- Account–niche mapping has a composite primary key and foreign keys to profile and niche.
- A partial unique index enforces at most one active primary niche per account.
- Learning snapshot period bounds are checked.
- Learning snapshot FK ensures the account/niche pair exists in the mapping table.
- Aggregate period uniqueness prevents duplicate snapshots for the same account/niche/window.
- Migration runner sorts migration filenames lexically and records the filename as its migration version. The two existing 009-prefixed files are unique filenames, so the current runner can distinguish them. 013 sorts after 012.
- No down-migration mechanism was found. Rollback therefore needs a reviewed operational/forward-fix strategy, not an assumed automatic downgrade.

## 3. Schema decisions and remaining implementation constraints

### 3.1 Account ownership — owner decision received

**Owner selected A: one owner/operator manages multiple Pinterest accounts.** Model 2 is deployment-scoped to one operator; it will not introduce a multi-tenant user table, synthetic owner IDs, or independent tenant claims. Each Pinterest account remains independently keyed by its canonical pinterest:<user_id> ID.

The existing shared API key remains service authentication, not proof of a distinct human identity. Registry write routes must remain behind the existing protected operator/service boundary and must not claim multi-user isolation. Audit records must not invent a human actor identity.

### 3.2 Credential linkage and metadata-only lookup

The revised draft constrains profiles to the canonical pinterest: namespace and adds a restrictive FK to pinterest_credentials(account_id). The suffix is not forced to numeric-only because current test and legacy code contracts permit nonnumeric test identifiers.

Existing credential getters still decrypt and return token material. A metadata-only connected-account lookup remains a Phase 4 repository/vault gap. Profile status means operator-controlled Model 2 activation (active|paused); live credential status must be read from existing credential metadata on each protected operation. A revoked credential must never be treated as connected merely because a profile is active.

### 3.3 Publication-to-niche attribution added to the draft

The revised draft adds model2_publication_niche_attributions, keyed by publication_id, with restrictive composite FKs to pin_publications(id, account_id) and the exact model2_account_niches(account_id, niche_id) assignment. A non-partial unique index on pin_publications(id, account_id) supports the composite FK. Attribution rows are immutable; legacy publications with NULL account_id cannot be attributed by this relation. A further lineage table, model2_learning_snapshot_sources, records the exact raw pin_analytics_snapshots.id, publication_id, account_id and niche_id for each learning snapshot. Composite FKs require the source analytics row, publication attribution and aggregate account/niche to agree. Deferred constraint triggers validate at commit that source_snapshot_count equals source rows and sample_size equals distinct contributing publications. Source lineage rows are immutable and copy the exact source metrics through a BEFORE INSERT trigger. This is necessary because Model 1 updates a raw analytics row in place when the same Pin/date window is fetched again; the copied JSONB preserves the historical values actually consumed.

Gateway integration is not implemented yet. Phase 6 must insert attribution in the same PostgreSQL transaction that reserves the publication row, before any Pinterest network request. Raw analytics remain joined through publication_id; the projection must join through this explicit attribution table. No inference from product text, prompts or caller filters is permitted.

### 3.4 JSONB contracts narrowed

- Account–niche settings are restricted to the empty object until a concrete setting contract is approved; 1 KiB bound.
- Learning metrics are limited to the existing Learning Loop's four keys: impression, save, pin_click, outbound_click; 4 KiB bound; values must be nonnegative JSON numbers or JSON null. Unknown metrics cannot be added silently.
- source_snapshot_count >= sample_size >= 0 is enforced. Phase 7 must define sample_size as unique attributed publications and source_snapshot_count as contributing raw snapshots; tests must verify this interpretation. Missing metrics remain NULL/unknown, never zero.

### 3.5 Timezone and status consistency

- SQL retains a bounded timezone string; onboarding/update must reuse the existing ZoneInfo validator in app/affiliate_scheduler.py.
- Profile status is only active|paused; credential status remains authoritative in pinterest_credentials and must be checked through the metadata-only lookup on every protected operation.
- Mapping activation must transactionally require an active profile and active niche. Reads/projections must exclude paused profiles, paused mappings, archived niches and revoked credentials. No new timezone package is needed.

### 3.6 Deletion and historical evidence

- Revised FKs use ON DELETE RESTRICT; account profiles, mappings, attributions and learning snapshots are not silently cascade-deleted. Niches use archival; mappings use pause; profiles use pause.
- Publication attribution is immutable and timestamped. The existing shared API key does not provide a reliable human actor identity, so the schema deliberately does not fabricate created_by_user_id. A richer actor audit trail requires an explicit identity design before implementation.
- Retention and any legal deletion workflow remain a separate owner-approved policy; no destructive deletion endpoint is in scope.

### 3.7 Region taxonomy

The existing Agent trends/featured-topics validators explicitly support exactly US and GB+IE. The revised schema reuses this already-implemented contract rather than inventing a second taxonomy. Any future expansion must update the existing provider/domain contract and Model 2 schema together.

## 4. Existing-system constraints the new schema must respect

- `pinterest_credentials.account_id` is unique and has status `connected|revoked`.
- `pin_publications.account_id` is nullable for legacy rows; legacy NULL must not be guessed.
- `pin_publications` uniqueness is `(content_version_id, board_id)`, and publication account mismatch is guarded by the existing gateway.
- `pin_analytics_snapshots.publication_id` is the authoritative join from raw Pin metrics to a publication.
- Scheduler enforces one active schedule per account, not per niche. It has no niche ID. Do not silently change its quota behavior in this migration.
- Existing product/content workflow and publication gateway must remain the only source of Pin creation and publication state.

## 5. Existing draft tests — review

Files already present:
- `tests/test_model2_registry_migration.py`
- `tests/test_model2_registry_postgres.py`

Current coverage in source:
- Static tests now cover six tables, credential FK, publication/account composite FK, attribution immutability, JSONB bounds, primary-niche uniqueness, source metrics capture, deferred count triggers and forbidden Model 1 writes. Their four test functions were manually invoked and passed.
- Disposable PostgreSQL test source covers account/niche membership FK, one active primary niche and account separation; the fixture now creates disposable credential metadata rows and narrows expected constraint exceptions.

Remaining test gaps:
- No live disposable-PostgreSQL run has verified migration syntax, credential FK, composite publication FK, deferred source-count triggers, immutability triggers or JSONB constraints.
- PostgreSQL test source now creates disposable credentials, products, content versions, publications and raw analytics rows to verify credential/profile linkage, lineage capture, immutable source/attribution, deferred count rejection and cross-account FK rejection; it has not been executed in this environment.
- No test yet verifies credential revocation through a future metadata-only repository method.
- No test yet verifies invalid IANA timezone rejection or pause/archive behavior in repository logic.
- The fixture uses TEST_DATABASE_URL only and never falls back to DATABASE_URL; the URL must still be independently verified as disposable before use.
- Broad exception assertions have been narrowed to psycopg ForeignKeyViolation and UniqueViolation.
- The four static test functions were manually invoked and passed; pytest itself is unavailable, so pytest collection/execution has not run.

## 6. Open-source reuse decision

No additional package is needed for this schema work:
- Existing FastAPI/Pydantic models cover route/domain validation.
- Existing Psycopg 3 transaction/pool layer covers PostgreSQL access.
- Existing Python `zoneinfo` covers IANA timezone validation.
- PostgreSQL constraints, indexes and JSONB cover relational integrity and bounded structured data when defined correctly.
- Existing credential vault is reused; only a metadata-only lookup capability is missing.

Do not add SQLAlchemy, pandas, a second migration framework, a niche taxonomy package, or a timezone package without a demonstrated requirement. No candidate external package has been selected or installed.

## 7. Phase 2 exit gate

**IN PROGRESS — schema draft revised; disposable PostgreSQL verification unavailable**

Owner decision A (single operator, multiple Pinterest accounts) is recorded. The schema draft now contains six additive tables, explicit publication attribution, immutable raw analytics lineage, deferred count validation and bounded metrics. Phase 2 can close only after:

1. Execute the complete migration sequence, including migration 013, against a verified disposable PostgreSQL 16 database using the repository migration runner.
2. Run the focused static and PostgreSQL tests; verify account/credential FK, canonical account ID checks, primary-niche uniqueness, publication/account/niche composite FKs, raw analytics lineage, source-metric capture, immutable history and deferred count constraints.
3. Verify fixture cleanup leaves no test rows and never touches a non-disposable database. TEST_DATABASE_URL must be explicitly set and independently confirmed as a disposable test database; never fall back to DATABASE_URL.
4. Record a forward-fix/backup recovery plan because the repository has no down-migration runner.
5. Obtain final owner acceptance of the reviewed schema contract before moving to Phase 3 or applying migration 013 anywhere.

Future implementation constraints (not Phase 2 exit blockers): Phase 4 must add a metadata-only credential lookup; Phase 6 must write publication attribution in the existing gateway reservation transaction before Pinterest network I/O; application repositories must validate IANA timezones and active/paused/archive state transitions. No new publisher, vault, ledger, analytics ingestion path or scheduler is permitted.

## 8. Safety confirmation

Migration 013 and its static/PostgreSQL test drafts were revised in the isolated worktree only after owner decision A. The four static test functions were manually executed and passed; pytest and PostgreSQL tests remain unrun. No application source code was changed. No PostgreSQL instance was connected. No production DB operation, deployment, commit/push/PR/merge, OAuth operation, Pinterest API write, Pin or Board creation occurred.

## 9. Additional concurrency and test-isolation findings — 2026-11-08

A further source-only review identified two items that must be resolved or explicitly constrained before Phase 2 approval:

1. **Concurrent lineage insertion can bypass the deferred count invariant.** The deferred constraint trigger currently counts source rows but does not serialize writers on the parent `model2_learning_snapshots` row. Two transactions can concurrently insert different source rows for the same already-committed learning snapshot. Under READ COMMITTED, each transaction's deferred count query may see its own row but not the other transaction's uncommitted row; both can satisfy the expected count and commit, leaving the final committed source count too high. The draft needs a parent-row serialization strategy (preferably lock the learning snapshot row before accepting a source insert, with a documented lock order) and a real two-connection PostgreSQL regression test. Do not claim the deferred count invariant is concurrency-safe until that test passes.
2. **PostgreSQL fixture cleanup is database-wide for the two immutable lineage tables.** The fixture truncates `model2_learning_snapshot_sources` and `model2_publication_niche_attributions` because row-level immutability prevents ordinary deletion. This is acceptable only in a dedicated disposable test database and with tests serialized; parallel fixtures could truncate one another's rows. Before execution, independently verify the database is disposable, confirm `TEST_DATABASE_URL` is not simply inherited from `DATABASE_URL`, and run this test file without parallel workers. A future fixture redesign should avoid global truncation if parallel execution is required.

These are review findings, not verified runtime failures: no PostgreSQL instance is available in the current environment, so neither concurrency behavior nor cleanup isolation has been exercised. Migration 013 remains unchanged and unapplied. Phase 2 remains IN PROGRESS.


## 10. Parent-row serialization implemented in draft — 2026-11-08

- Added `model2_lock_learning_snapshot_source_parent()` and a `BEFORE INSERT` trigger on `model2_learning_snapshot_sources`. Each source insert now locks its parent `model2_learning_snapshots` row with `SELECT ... FOR UPDATE` before the row is accepted. Concurrent writers targeting the same snapshot therefore serialize before the deferred count validation runs.
- The SQL comment documents lock ordering: callers inserting sources for multiple snapshots should process `learning_snapshot_id` values in ascending order to reduce cross-snapshot deadlock risk. PostgreSQL can still abort a deadlocked transaction; the application must treat that as a retryable transaction failure, never bypass validation.
- Added static regression `test_model2_learning_source_writers_serialize_on_parent_snapshot` and a real two-connection PostgreSQL regression source. The latter deliberately holds the first writer's transaction open, starts a second writer for the same one-source snapshot, asserts the second writer blocks, then releases the first and expects the second commit to fail the deferred count invariant. The final persisted source/publication count must remain exactly one.
- Verification performed after this draft change: all five static migration test functions manually executed and passed; both test files passed `py_compile`; `git diff --check` passed.
- Runtime verification remains unavailable: `TEST_DATABASE_URL` and `DATABASE_URL` are unset; `pytest`, `psycopg`, `psycopg_pool`, `psql`, `postgres` and `initdb` are unavailable. No database was contacted. The new concurrency test is authored but **NOT RUN**. The race is addressed in the proposed SQL design, not yet proven by PostgreSQL execution.
- The fixture's global TRUNCATE cleanup risk remains. PostgreSQL tests must run serially against a separately verified disposable database; do not configure TEST_DATABASE_URL by copying DATABASE_URL. Phase 2 remains IN PROGRESS and migration 013 remains unapplied.


## 11. Versioned parent serialization and local PostgreSQL provisioning result — 2026-11-08

### Concurrency design supersedes the SELECT FOR UPDATE draft in section 10

- Replaced the source-parent `SELECT ... FOR UPDATE` with a versioned parent-row `UPDATE` in `model2_lock_learning_snapshot_source_parent()`.
- Added internal `source_lock_version BIGINT NOT NULL DEFAULT 0 CHECK (source_lock_version >= 0)` to `model2_learning_snapshots`. Every source-row insert increments this version in its BEFORE INSERT trigger. This creates a new parent tuple version as well as taking the row lock.
- Under READ COMMITTED, a waiting writer proceeds against the newly committed parent version and its deferred count check sees the earlier committed source; if the extra source exceeds the declared count, its transaction is rejected by the deferred constraint trigger.
- Under REPEATABLE READ / SERIALIZABLE, a writer whose transaction snapshot predates the concurrent parent-row update must fail with SQLSTATE 40001 (Psycopg `SerializationFailure`) and retry the whole transaction. This avoids relying on a row lock alone, which would not refresh an old REPEATABLE READ snapshot.
- Updated the PostgreSQL regression test to cover both READ COMMITTED (expect deferred `RaiseException`) and REPEATABLE READ (expect `SerializationFailure`). The test establishes the second transaction's snapshot before the first commits and observes a real blocker via `pg_blocking_pids()` before releasing writer one. It then asserts only one source/publication remains committed.
- This is a stronger draft-level invariant than the SELECT FOR UPDATE proposal in section 10. Runtime verification remains required; no claim of PostgreSQL behavior is made until the test executes on a real server.

### Disposable PostgreSQL provisioning attempt

- Owner approved provisioning a local test-only PostgreSQL environment. Device is Debian 12 ARM64, with about 8.1 GB free disk. Installed PostgreSQL server/client **16.15** from the official PostgreSQL APT repository after verifying the repository signing-key fingerprint `B97B 0AFC AA1A 47F0 44F2 44A0 7FCC 7D46 ACCC 4CF8`.
- Created external test virtual environment `/root/.venvs/model2-pg16` with pytest 9.2.0, Psycopg 3.3.8, psycopg-pool 3.3.3, Pydantic Settings 2.16.2 and pglast 8.7. No project requirements or lockfiles were modified.
- PostgreSQL server cluster initialization is blocked by the device kernel: initdb fails with `could not create shared memory segment: Function not implemented`, `shmget(...)`; `/proc/sys/kernel/shmmax` and `shmall` are absent, and `unshare -Ur` fails with `Invalid argument`. Attempting mmap/huge-pages configuration did not bypass the kernel's SysV IPC restriction. No PostgreSQL server started and no database was created.
- PostgreSQL package post-install also could not create its default cluster; `pg_lsclusters` reports no cluster. No database migration ran. `TEST_DATABASE_URL` remains unset; `DATABASE_URL` was unset. All tests were run from `/tmp` with secret-bearing environment variables explicitly unset so Pydantic did not load the repository `.env` file.

### Verification results after the latest migration/test edits

- `pytest -q` on both Model 2 test files: **5 passed, 9 skipped**. All 5 static tests passed. All 9 PostgreSQL integration cases were skipped because `TEST_DATABASE_URL` is intentionally unset; this is not a database test pass.
- Python compilation for both test files: PASS.
- `pglast 8.7` PostgreSQL grammar parse: **14/14 numbered migration files parsed**, including migration 013.
- `pglast.parser.parse_plpgsql_json`: **5/5 PL/pgSQL functions in migration 013 parsed**.
- `git diff --check`: PASS.
- SQL grammar parsing does not execute DDL, resolve live FK dependencies, validate trigger timing/transaction behavior or prove the concurrency invariant. PostgreSQL integration tests remain NOT RUN.
- Phase 2 remains **IN PROGRESS / NOT CLOSED**. Next required environment is a Linux host/CI runner with working PostgreSQL 16 shared memory/IPC and correct filesystem ownership. Run the full migration sequence and both concurrency isolation cases there against a verified disposable DB; keep the fixture serial because teardown truncates immutable lineage tables. No production DB use or migration is authorized.


## 12. Dedicated GitHub Actions PostgreSQL 16 workflow — 2026-11-08

- Added `.github/workflows/model2-postgres-integration.yml` to the isolated Model 2 feature branch.
- Triggers only on pushes to `feat/model2-open-source-reuse`, pull requests targeting `main`, and manual dispatch. It does not alter existing CI workflow triggers.
- Uses a GitHub-hosted Ubuntu runner and an ephemeral `postgres:16` service with a dedicated `model2_test` database. No Neon, production `DATABASE_URL`, GitHub secrets, Pinterest OAuth or provider credentials are used.
- Explicitly sets `DATABASE_URL` to empty and `TEST_DATABASE_URL` to the loopback-only disposable service. A preflight asserts scheme, loopback host, port 5432, database name and test user before pytest starts.
- Runs only `tests/test_model2_registry_migration.py` and `tests/test_model2_registry_postgres.py`. The PostgreSQL fixture invokes the repository migration runner, which applies the complete numbered migration sequence (001–013) to the ephemeral database, then exercises the registry, FK, attribution, raw analytics lineage, immutability, deferred counts and two-connection concurrency tests.
- The test file is run without xdist/parallel workers because fixture teardown truncates immutable history tables across the disposable database.
- Local checks after adding workflow: Python compile PASS; `pytest` 5 passed / 9 skipped (integration skipped locally because no local PostgreSQL server); `git diff --check` PASS. A YAML parser was not yet available locally; GitHub Actions execution will be the authoritative workflow parse/run check. PostgreSQL runtime results are still pending.
- Owner explicitly approved adding this workflow and pushing only the Model 2 feature branch. No PR creation, merge, deployment or production DB action is included in that approval.

- While preparing the CI workflow, reviewed fixture teardown and found the new concurrency test's `-race-1` / `-race-2` suffixes would not match exact-equality cleanup predicates. Updated cleanup predicates to match the complete per-test suffix prefix for raw analytics, publications, products and content versions; added a static regression assertion. Latest local result: **6 static tests passed, 9 PostgreSQL integration tests skipped** (no local DB); workflow YAML parsed successfully with PyYAML; `git diff --check` passed.


## 13. First GitHub-hosted PostgreSQL execution — 2026-11-08

- Dedicated workflow executed on commit `2d418fcee3ea12f99b6268b21fddebff5e189536`, run `42497549120` (https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42497549120). PostgreSQL 16 service started healthy; migration runner applied the numbered migration sequence sufficiently for the Model 2 test cases to execute. Database-target preflight passed; dependency installation passed.
- Actual result: **12 passed, 3 failed**. Two root causes identified from test output:
  1. The negative account–niche FK test attempted to create a second primary niche, so the partial unique index correctly rejected it before the expected FK. Changed that negative test row to `is_primary=FALSE`; primary uniqueness remains separately tested.
  2. Concurrency test initially committed a learning snapshot declaring one source before inserting any source row. The deferred count trigger correctly rejected the inconsistent snapshot at that commit. Changed the test to create the snapshot with zero counts, then in writer one insert its first source and update expected counts to one within the same transaction before waiting. This creates a valid committed baseline for the second writer to race against.
- The three failed cases were one negative FK test and the two isolation-level concurrency cases. The other 12 cases passed, including full test module collection, most registry constraints and lineage checks. This is the first actual PostgreSQL runtime execution; do not describe the first run as passing.
- Follow-up local checks after correcting the test setup: **6 static tests passed, 9 PostgreSQL tests skipped locally** because the Android kernel still cannot run PostgreSQL. Python compile, YAML parse, and `git diff --check` passed. The corrected database tests have not yet been rerun on GitHub.
- Next: commit only the corrected PostgreSQL test and synchronized evidence notes to `feat/model2-open-source-reuse`, then verify the next workflow run and inspect both concurrency isolation outcomes. Phase 2 remains **IN PROGRESS / NOT CLOSED** until the complete focused PostgreSQL suite passes.


## 14. Second GitHub PostgreSQL run — follow-up test corrections — 2026-11-08

- Second workflow run `42497741517` on commit `ac731fc6efd540ab9b3373e8bcb73306bbd081f4` still failed: **12 passed, 3 failed**. The new log clarified two additional test-code defects; no migration SQL change was made.
  1. The account–niche test incorrectly expected that an account could not be assigned a second non-primary niche. That contradicts the intended multi-niche registry. Corrected it to assert that an account may be assigned another niche with `is_primary=FALSE`, after which a snapshot for that explicit mapping is valid. The separate test still verifies only one active primary niche.
  2. The concurrency test used dictionary-style row access on direct `psycopg.connect()` connections, whose default row factory returns tuples. The second writer therefore failed before signaling readiness. Corrected both PID and blocker-count reads to positional tuple access.
- Latest local verification after these corrections: **6 static tests passed, 9 PostgreSQL integration tests skipped** (local PostgreSQL remains unavailable); Python compilation and `git diff --check` passed. Corrected database cases are not yet verified on a PostgreSQL server.
- Next: push only the corrected test and evidence notes to the same Model 2 feature branch, then inspect the third workflow run. Phase 2 remains **IN PROGRESS / NOT CLOSED**.


## 15. Third GitHub PostgreSQL run — concurrency regression passes — 2026-11-08

- Third workflow run `42497944796` on commit `eceecc2be3bbc6d93700eb590d27de332a5c2d04` completed successfully: **15 passed, 0 failed, 0 skipped** on a healthy GitHub-hosted PostgreSQL 16.15 service.
- This includes all 6 static migration tests and all 9 PostgreSQL integration cases, including the two-connection race tests under READ COMMITTED and REPEATABLE READ. The test fixture calls the repository's actual `database.run_migrations()` against the fresh disposable service; all test cases completed.
- The first CI run exposed a deferred-count setup issue; the second exposed a mistaken expectation that a second non-primary niche assignment should be rejected and tuple-vs-dict row access in the concurrency probe. Both were corrected without changing migration SQL. Third run is the first full green database run.
- Added one final workflow gate after the green run: compare `schema_migrations` against every numbered migration file and query for leftover test account/niche/learning/analytics/publication/product/content rows. This makes migration-ledger completeness and fixture cleanup explicit rather than inferred only from pytest completion. YAML and embedded Python parse/compile locally; this new post-test gate awaits its own GitHub run.
- Current Phase 2 status remains **IN PROGRESS / NOT CLOSED** until the new ledger/cleanup workflow gate passes, forward-fix recovery plan is documented, and owner explicitly accepts the schema contract. No migration was applied to any non-disposable database.


## 16. Forward-fix and recovery plan — 2026-11-08

- Migration 013 is additive: it creates Model 2 registry/attribution/learning tables, supporting indexes, functions and triggers. It does not backfill legacy publication rows or mutate credential, scheduler, publication or raw analytics data. No down-migration is supplied; do not invent a destructive rollback.
- The repository migration runner uses one pooled PostgreSQL connection and one transaction for the migration invocation; it records each migration version only after that migration SQL succeeds. A SQL error before transaction completion should roll back the invocation's uncommitted DDL and ledger writes. This behavior follows from the current runner's transaction boundary; verify again if runner behavior changes.
- Disposable CI recovery: the service database is ephemeral and destroyed with the job. On any failure, preserve the logs and fix the migration/test forward in the feature branch; rerun from a fresh PostgreSQL 16 service.
- Before any future non-disposable application (not currently authorized): take and verify a restorable database snapshot/backup; rehearse the exact migration sequence on a restored isolated clone; verify all prior migration ledger entries and the 013 schema objects; record the target commit, DB identity, backup identifier and operator approval; then apply through the repository migration runner in a separately approved maintenance window.
- If migration 013 fails during its transaction, stop and inspect the error; do not manually mark it applied or drop pre-existing Model 1 objects. Correct the migration in a reviewed forward-fix commit and retry on a fresh clone first.
- If 013 has committed and a later defect is found, prefer a new numbered forward-fix migration with an explicit repair test. Restore the backup only when no post-backup application writes need preservation and owner approves the restore; otherwise forward-fix to avoid discarding live data. Do not run ad-hoc destructive SQL or delete historical attribution/learning rows.
- Production or any persistent shared database remains out of scope. The only current authorization is temporary GitHub Actions testing and pushing to `feat/model2-open-source-reuse`; production migration requires separate explicit owner approval.


## 17. Final isolated PostgreSQL gate — 2026-11-08

- Workflow run `42498159463` on commit `7c83183ba30fad5d4a85687237b6d58c1f46257b` completed successfully on GitHub Actions with PostgreSQL 16.15.
- Test result: **15 passed, 0 failed, 0 skipped** (6 static + 9 PostgreSQL integration tests). Both concurrency isolation cases passed.
- Post-test verification passed: `schema_migrations` contains all **14/14 numbered migration files**; synthetic Model 2 credentials, profiles, niches, mappings, learning snapshots, sources, attributions and synthetic Model 1 analytics/publications/products/content rows all have zero leftovers after fixture teardown.
- The test target preflight passed with `DATABASE_URL` empty and `TEST_DATABASE_URL` restricted to loopback PostgreSQL database `model2_test`. The PostgreSQL service was ephemeral and stopped at job completion. No Neon/production DB or Pinterest credentials/provider endpoints were involved.
- Forward-fix/recovery plan is documented in section 16. SQL parse, PL/pgSQL parse, local static tests, YAML parse and diff checks were also previously recorded.
- **Phase 2 technical exit gates are now satisfied** for the draft schema: migration runner applied the full numbered sequence on a fresh disposable PostgreSQL 16 database; all focused tests and concurrency cases passed; the CI ledger and cleanup gate passed; recovery plan is documented. **Phase 2 is not formally closed yet:** owner acceptance of the final schema contract is still required before Phase 3. No persistent database or production migration is authorized.
