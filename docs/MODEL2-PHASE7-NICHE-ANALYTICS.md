# Model 2 Phase 7 — Niche Analytics Projection

**Status:** IN PROGRESS — implementation added; local unit/API suite passes; disposable PostgreSQL CI gate pending.
**Started:** 2026-11-09
**Architecture authority:** docs/MODEL2-FOUNDATION.md (FROZEN)
**Prerequisite:** Phase 6 closed; see docs/MODEL2-PHASE6-NICHE-CONTEXT.md.

## 1. Existing sources and schema reuse

- Model 1 raw Pin analytics: pin_analytics_snapshots, populated by app/learning.py.
- Actual successful Pin/publication and account: pin_publications.
- Immutable niche attribution: model2_publication_niche_attributions, written atomically by the existing publishing gateway.
- Model 2 aggregate and exact source lineage: model2_learning_snapshots and model2_learning_snapshot_sources, introduced and PostgreSQL-verified in migration 013.
- Existing Psycopg 3 transaction/pool, JSONB and PostgreSQL aggregation are sufficient. No new dependency, raw analytics table, migration, ML framework or external service is justified.

## 2. Projection semantics

- A projection is requested for one exact canonical account ID, one niche ID and exact raw analytics period bounds.
- Raw analytics period matching is exact (period_start and period_end both equal the requested bounds). No partial-overlap arithmetic or mixing different observation windows.
- Include only raw analytics rows whose publication belongs to the requested account and has immutable attribution to the requested niche. Never infer attribution from product/category/prompt text.
- Do not filter historical attribution by current active/paused/archived state. Historical evidence remains queryable after an account, assignment or niche is paused/archived.
- Lock selected raw analytics rows FOR SHARE during projection. This prevents Model 1's ON CONFLICT DO UPDATE refresh from changing the metrics between selection and the source-capture trigger.
- sample_size is the number of distinct publications contributing at least one raw analytics row.
- source_snapshot_count is the exact number of raw analytics rows captured.
- Allowed aggregate metrics remain exactly impression, save, pin_click, outbound_click.
- For each metric, sum only when every source row contains a numeric value. If any source has NULL or lacks that metric, the aggregate is NULL/unknown. Never substitute zero or report a partial sum as complete.
- Numeric aggregation uses decimal arithmetic; serialize integral totals as integers and fractional totals as JSON numbers.
- learning_status is descriptive_only for a materialized snapshot with one or more source publications. No predictive model is trained.
- If no attributed raw rows exist for the exact period, return insufficient_data without inserting an empty snapshot. This allows a later run, after raw analytics arrive, to create the period snapshot.

## 3. Idempotency and immutability

- The existing unique key (account_id, niche_id, period_start, period_end) makes projection one-time per exact period.
- First successful projection inserts the parent aggregate and all source rows in one transaction.
- The source-capture trigger copies the exact raw JSONB metrics into immutable source lineage.
- If a snapshot for the same account/niche/period already exists, return that persisted snapshot unchanged (created=false). Do not refresh, delete or rewrite immutable source rows.
- A new raw analytics observation window produces a new period snapshot. Repeated calls for the same period do not mutate historical evidence.
- Deferred database constraints verify sample_size and source_snapshot_count against actual inserted source rows at transaction commit.

## 4. Account isolation and API boundary

- Add a protected projection trigger endpoint under /model2/learning/snapshots; it writes only the derived Model 2 snapshot and never calls Pinterest or the Learning Loop provider.
- Add a protected read endpoint scoped by exact account and niche for persisted snapshots.
- Both endpoints reuse app/auth.py fail-closed API-key dependency.
- Repository SQL always filters by exact account and niche; path/body identifiers must match where both are present.
- Historical paused/archived mappings remain eligible for reading and projecting previously attributed data; a mapping must still exist by FK.
- No global/cross-account aggregation, autonomous action, scheduling or predictive ML.

## 5. Required tests

- Pure aggregation tests: complete metrics sum; one missing metric makes only that metric unknown; missing values are not zero; decimal totals are stable; unsupported keys/invalid numbers are rejected.
- PostgreSQL tests: exact account+niche attribution; exact period boundaries; unrelated/unattributed publications excluded; source row counts and distinct publication counts; source trigger copies metrics; source metrics remain unchanged after Model 1 raw row update; same-period call is idempotent; deferred constraints pass; account isolation.
- API tests: fail-closed authentication, exact account/niche scoping, missing mapping, no external publisher/provider calls.
- Full existing Model 1 and Model 2 regression suite.
- GitHub Actions disposable PostgreSQL run and zero-fixture cleanup gate.

## 6. Exit gate

Phase 7 remains IN PROGRESS until local tests and exact-head feature-branch CI pass, including PostgreSQL source-lineage, aggregation and cleanup checks. No production DB, migration, provider call, OAuth action, Pin/Board write, PR, merge or deployment is authorized.


## 7. Implementation checkpoint — 2026-11-09

Implemented in the isolated Model 2 feature worktree:

- Added app/model2_learning.py with a pure metric aggregator, transaction-safe projection writer, account+niche-scoped snapshot reader and protected API routes.
- Registered the router in app/main.py. POST /model2/learning/snapshots materializes a derived snapshot; GET /model2/learning/accounts/{account_id}/niches/{niche_id}/snapshots reads only the exact pair. Both use the existing fail-closed API-key dependency.
- Projection requires an existing exact account–niche mapping, but intentionally does not filter current active/paused/archived state so historical attributed evidence remains usable.
- Source query joins exact account, publication, immutable attribution and exact period; it includes only confirmed succeeded publications whose stored Pin ID matches the raw analytics row.
- Selected raw analytics and publication rows are held FOR SHARE until the projection transaction completes. Model 1 raw refresh cannot change the evidence between aggregation and the source-capture trigger.
- Aggregates use the four existing Learning Loop keys. A metric is summed only if every source row supplies a numeric value; missing values remain NULL. Invalid/unsupported keys and invalid numbers are rejected.
- The projection stores one immutable snapshot per exact account+niche+period using the existing unique key. Source rows are inserted in the same transaction and their trigger copies exact raw metrics. Repeated same-period requests return the existing snapshot unchanged.
- If there are no eligible raw rows, the endpoint returns insufficient_data with NULL metrics and zero counts but does not persist an empty snapshot.
- No migration or dependency was added. Existing PostgreSQL JSONB, triggers, FKs, Psycopg transactions and immutable lineage are reused.
- Added pure aggregation tests, protected API tests and disposable PostgreSQL tests for account/niche/period isolation, missing metrics, exact source capture, raw refresh immutability, same-period idempotency, pending publication exclusion and historical paused/archived mappings.
- Dedicated GitHub Actions workflow now includes the new pure/API tests and the expanded PostgreSQL integration suite.

### Local evidence

- Focused projection/API tests: **18 passed, 28 skipped**; the skipped cases are PostgreSQL integration tests because TEST_DATABASE_URL is unset.
- Full local repository suite: **274 passed, 48 skipped, 1 warning**.
- Python compileall, CI workflow YAML parsing, required test-target check and git diff --check are pending final pre-push check.
- The PostgreSQL projection/source-lineage tests have not yet executed locally; exact-head GitHub Actions disposable PostgreSQL CI is the authoritative next gate.

No production DB/migration, Pinterest provider request, OAuth action, Pin/Board write, PR, merge or deployment occurred.


## 7. Implementation checkpoint — 2026-11-09

Implemented in the isolated Model 2 feature worktree:

- Added app/model2_learning.py with bounded request/response contracts, strict canonical account ID validation, exact account+niche repository scoping, protected projection/read endpoints and pure descriptive aggregation.
- Projection reads only exact period_start/period_end rows joined to the exact account publication and immutable niche attribution. Only successful publications whose Pinterest Pin ID matches the raw analytics row are eligible. Pending/failed/unattributed publications are excluded.
- Raw analytics and publication rows are locked FOR SHARE during source selection so Model 1 in-place analytics refresh cannot race the source-capture trigger. The migration 013 trigger copies exact raw metrics into immutable source rows.
- sample_size counts distinct publications; source_snapshot_count counts raw analytics rows. Each metric is summed only if every source row contains a numeric value; missing/null stays unknown, not zero. Unsupported metric keys, booleans, non-numeric, negative and non-finite values are rejected.
- Exact-period snapshots are idempotent and immutable. Empty periods return insufficient_data without creating an empty snapshot. Existing paused/archived historical assignments remain queryable for historical attribution.
- Added API and pure aggregation tests, plus disposable PostgreSQL tests for account/niche/period isolation, source capture, raw-refresh lineage preservation, idempotency, empty periods, missing assignments, historical paused/archived mappings and pending publication exclusion.
- CI workflow includes the new Phase 7 API and aggregation tests and existing PostgreSQL integration suite.

### Local evidence

- Focused unit/API suite: 38 passed, 1 non-blocking Starlette/httpx TestClient deprecation warning.
- Full local suite: 274 passed, 48 skipped, 1 warning. PostgreSQL integration cases are skipped locally because DATABASE_URL, TEST_DATABASE_URL and PB10_TEST_DATABASE_URL are unset; no database was contacted locally.
- Python compilation and git diff --check passed.
- Disposable PostgreSQL execution for the new Phase 7 integration cases remains pending in GitHub Actions. Phase 7 remains IN PROGRESS until exact-head CI and fixture cleanup pass.

No production DB, migration, provider call, OAuth action, real Pin/Board, PR, merge or deployment has occurred.
