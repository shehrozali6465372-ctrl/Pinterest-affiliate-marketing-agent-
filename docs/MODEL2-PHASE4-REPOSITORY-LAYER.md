# Model 2 Phase 4 — Repository Layer

**Status:** IN PROGRESS — implementation and isolated unit tests written; PostgreSQL CI gate pending.
**Started:** 2026-11-09
**Architecture authority:** `docs/MODEL2-FOUNDATION.md` (FROZEN)
**Prerequisite:** Phase 3 closed; see `docs/MODEL2-PHASE3-DOMAIN-CONTRACTS.md`.

## 1. Existing persistence capability inventory

| Need | Existing implementation | Decision |
|---|---|---|
| PostgreSQL pool and connection lifecycle | `app/database.py:get_pool`, `connection`, `close_pool` | Reuse; no second pool |
| Transaction/commit/rollback | Psycopg 3 connection context used by `app/database.py` repository functions | Reuse one pooled connection per repository operation; exception exits rollback |
| Dict row mapping | Pool configured with Psycopg `dict_row` | Reuse |
| SQL migration runner | `app/database.py:run_migrations` | Reuse; no Phase 4 migration |
| Credential storage | `app/credential_vault.py`, `pinterest_credentials` | Reuse as source of truth |
| Safe account-connected check | No metadata-only helper existed; `get_pinterest_credential` decrypts access token and may trigger refresh | Added metadata-only transaction helper; never use token getter for existence checks |
| Model 2 tables | Approved migration 013 | Use existing schema; no new table or migration |

No new dependency or persistence framework was justified. Psycopg 3 and the existing connection pool are sufficient.

## 2. Implemented repository boundary

New module: `app/model2_repository.py`.

Implemented operations:
- Save/create/update account profile metadata.
- Read one profile and list profiles.
- Create/update/read/list niche taxonomy entries.
- Save one account–niche assignment.
- List assignments for one exact canonical account ID.

Repository failures use explicit safe exception types: not found, conflict, and account-not-connected. The API layer can map these to HTTP responses in Phase 5 without exposing raw SQL/provider errors.

## 3. Credential-vault boundary

Added `pinterest_account_is_connected_in_transaction(conn, account_id)` to `app/credential_vault.py`.

- Executes only `SELECT account_id ... WHERE account_id=%s AND status='connected' FOR SHARE`.
- Does not select ciphertext, access/refresh token, scope or expiry fields.
- Does not instantiate AES-GCM, decrypt, call OAuth, or refresh tokens.
- `FOR SHARE` holds the connected-state row stable through the caller's transaction, so a concurrent status update waits until that operation commits/rolls back.
- Repository onboarding and activation use this helper inside their existing transaction. Pausing an existing profile remains possible after credential revocation; reactivation requires a currently connected credential.
- No token getter is called by Model 2 repository code.

## 4. Transaction and state invariants

- Profile writes use one pooled connection and one transaction. New profiles and active profiles require a connected credential. Pausing a profile also pauses active assignments, retaining rows and primary flags.
- Niche archival pauses active mappings without deleting mapping history. Reactivating a niche does not silently reactivate old mappings.
- Assignment writes lock the account profile row `FOR UPDATE` before evaluating profile/niche state. This serializes competing assignment writers for the same account.
- Active assignments require an active profile, active niche and connected credential.
- Paused assignments may remain attached to paused profiles or archived niches. A paused mapping may retain `is_primary=true`, matching the approved partial unique index.
- When an active primary is selected, the transaction clears the prior active primary for that account, then upserts the selected mapping. The parent profile lock serializes competing primary selections. Under REPEATABLE READ/SERIALIZABLE, PostgreSQL may return serialization failure; callers must retry the whole transaction.
- Every mapping read is filtered by the exact account ID. No global mapping listing is exposed.
- No row deletion or cascade behavior is added; Phase 2 restrictive FKs preserve history.

## 5. Tests and current evidence

New unit tests: `tests/test_model2_repository.py`.
Extended disposable PostgreSQL integration tests: `tests/test_model2_registry_postgres.py`.
Dedicated workflow now runs domain, repository, migration and PostgreSQL test modules: `.github/workflows/model2-postgres-integration.yml`.

Unit/migration test run:
- **51 passed, 16 skipped**.
- 16 skips are PostgreSQL integration tests gated on `TEST_DATABASE_URL`; no local DB was contacted.

Full repository run after repository implementation:
- **218 passed, 34 skipped, 1 warning**.
- All DB integration tests were skipped because `DATABASE_URL`, `TEST_DATABASE_URL` and `PB10_TEST_DATABASE_URL` were unset.
- Existing non-blocking Starlette/httpx TestClient deprecation warning remains.

The 7 new PostgreSQL integration scenarios cover:
1. Metadata-only account onboarding with dummy ciphertext and no encryption key.
2. Refusal to reactivate a profile after credential revocation; pause remains allowed and pauses mappings.
3. Primary swap plus account-scoped listing and cross-account independence.
4. Niche archival pauses mappings without deleting history.
5. Active assignment to an archived niche is rejected.
6. Two concurrent primary selections for one account serialize to exactly one active primary.
7. Active assignments are rejected after the account credential is revoked.

**Important:** These seven database scenarios have not yet executed locally. They require the dedicated disposable PostgreSQL 16 GitHub Actions service. Do not label them passed until that workflow run succeeds.

## 6. Security and scope boundaries

- No production or Neon database access; no migration 014 or schema change.
- No credential decryption, OAuth refresh/rotation, Pinterest/provider request, publication, scheduler or Learning Loop invocation.
- No Pin/Board creation, image hosting, affiliate URL handling, or token/secret logging.
- Shared API key remains service authentication, not a distinct human identity. This layer does not claim multi-tenant ownership.
- Repository account scoping and connected-credential checks are not a substitute for the protected API boundary; Phase 5 must apply existing fail-closed service authentication consistently.
- No commit, push, PR, merge or deployment has been performed for Phase 4 at this checkpoint.

## 7. Phase 4 exit gate

Phase 4 remains IN PROGRESS until:
1. Unit tests and static checks pass.
2. The dedicated feature-branch PostgreSQL workflow runs all repository integration cases on fresh disposable PostgreSQL 16 and passes its migration-ledger/cleanup check.
3. Review exact CI commit and confirm no fixture rows remain.
4. Security review confirms all reads/writes are account-scoped, token metadata lookup is non-decrypting, and primary assignment concurrency is proven.

Next after Phase 4: Phase 5 — Protected Registry API. No API routes are added in Phase 4.
