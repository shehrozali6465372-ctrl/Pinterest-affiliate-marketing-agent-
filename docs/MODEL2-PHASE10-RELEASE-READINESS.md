# Model 2 Phase 10 — Release Readiness

**Status:** PRE-RELEASE REVIEW — NOT APPROVED FOR PRODUCTION RELEASE. R1 hardening and operator reconciliation are verified on exact feature-branch head; production migration/restore rehearsal and owner approvals remain open.

**Review date:** 2026-11-09  
**Feature branch:** `feat/model2-open-source-reuse`  
**Base production snapshot:** `785efd99849627062c1fff8504d21ca91abfee8e`

## 1. Scope and hard boundaries

This is a static/security and disposable-CI release-readiness review only. It does not authorize:

- applying migrations 014 or 015 to Neon or any shared/production database;
- deploying or merging Model 2;
- activating schedules, running due jobs, or invoking the scheduled worker against production;
- Pinterest API writes, OAuth refresh/reconnect/token rotation, or real Pin/Board creation;
- PR creation, merge, promotion or deployment.

No production credentials or database contents were read for this review.

## 2. Verified release evidence

- Phase 9 owner-approved implementation is on the isolated feature branch.
- Exact implementation CI commit `761204b7e5d09cce6eb5f26543602702d5db606a`, run `42536328716`: **212 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15.
- Docs closure commit `14e8e97c08fb1f61d93cf969e08cfe4cf9e9eb1d`, run `42536572870`: **212 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15.
- The Phase 9 runs recorded all 15 numbered migrations. The latest Phase 10 reconciliation run below records all 16 numbered migrations, verifies Model 2 and synthetic Model 1 fixture cleanup, and stops the ephemeral PostgreSQL container.
- Local full suite at the implementation checkpoint: **283 passed, 56 skipped, 1 non-blocking warning**. Local DB integration tests were skipped because `DATABASE_URL` and `TEST_DATABASE_URL` were unset. CI is the PostgreSQL evidence.
- Feature branch is isolated from `main`; no PR/merge/deploy.
- Latest exact-head Phase 10 run `42539115679`, commit `7c9b3484b73f43d40da492038569b0c28b12ad43`: **230 passed, 0 failed, 1 non-blocking warning** on disposable PostgreSQL 16.15. Includes endpoint authentication/validation tests and read-only inspection integration coverage. All 16 numbered migrations were recorded; fixture cleanup passed; PostgreSQL container stopped. Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42539115679
- Added migration 015, atomic account-checked scheduler-job reconciliation, read-only inspection, authenticated operator POST route, append-only audit and operator runbook `docs/MODEL2-SCHEDULER-RECONCILIATION-RUNBOOK.md`. No Pinterest/provider/workflow calls occur during reconciliation.


## 3. Security and operational findings

### R1 — Uncertain publication must consume quota and block replacement

**Severity:** High — release blocker.  
**Status:** Fix implemented and exact-head CI verified.

A scheduler job in `uncertain` may correspond to a Pin that Pinterest created even though the response was lost or ambiguous. Before hardening, account quota counted only `processing` and `succeeded`, and schedule replacement only blocked `queued`/`processing`. This could permit another Pin after an ambiguous result.

Hardening in this review:
- Model 2 account-local quota counts `uncertain` alongside `processing` and `succeeded`.
- An unresolved uncertain job blocks replacement of the account schedule, including on a later local day.
- A schedule with an uncertain job is not automatically marked completed.
- Existing legacy Model 1 quota behavior is not changed.
- Regression coverage verifies the uncertain result is never re-run, consumes the daily quota, and blocks replacement.
- Definite pre-publish conflicts are distinct from ambiguous publication outcomes: the worker treats only the explicit `niche_assignment_inactive` and `niche_account_not_connected` 409 codes as `failed` (not quota-consuming). Generic/ambiguous 409 and 502 outcomes remain `uncertain` and retain the fail-closed quota/replacement guard.
- Local full suite after this hardening: **283 passed, 57 skipped, 1 non-blocking warning**. PostgreSQL integration tests remain skipped locally because DB environment variables are unset; no DB was contacted.
- Exact-head implementation commit `5f818fa5adb5e3c45b1bd8f52d17926ae2ca2d8e`, GitHub Actions run `42536949741`: **213 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15. All 15 numbered migrations were recorded, Model 2 and synthetic Model 1 fixtures were cleaned, and the PostgreSQL container was stopped.

**Reconciliation now implemented and tested on the feature branch:**
- `GET /affiliate-scheduler/jobs/{job_id}/reconciliation?account_id=...` performs read-only ledger linkage inspection.
- `POST /affiliate-scheduler/jobs/{job_id}/reconcile` resolves only an `uncertain` job, checks the exact account and idempotency-key lineage, validates Model 2 niche attribution, and atomically updates publication ledger (when present), job state and append-only audit.
- Success requires one matching publication row and a verified Pin ID. Missing ledger cannot be marked succeeded. Confirmed absence requires explicit `confirm_pin_absent=true`; the job becomes terminal failed and the same key is never requeued.
- Recent pending rows, ambiguous candidates, account/product/niche mismatch, repeat reconciliation and transaction write failure are rejected/rolled back.
- Synthetic PostgreSQL regression matrix passed in run `42538656224`; no Pinterest Pin/Board was created.
- Operator instructions: `docs/MODEL2-SCHEDULER-RECONCILIATION-RUNBOOK.md`.

This resolves the reconciliation implementation blocker for isolated feature-branch readiness. It does not authorize production reconciliation or unattended scheduling.

### R2 — Scheduled worker is a production side-effect trigger

**Severity:** High — release gate.

`.github/workflows/affiliate-scheduler-worker.yml` contains an hourly GitHub Actions cron and calls the deployed Render `/affiliate-scheduler/run-due` endpoint with the service API key. It can execute queued jobs and publish Pins through the existing workflow. This review did not run or alter that workflow.

Before production release, the owner must explicitly approve when Model 2 schedules may be created/activated and when the worker may execute them. Do not use a live workflow dispatch as a test. Existing Model 1 scheduled behavior must be preserved and separately accounted for.

### R3 — Production migration rehearsal and rollback plan

**Severity:** High — release gate.

Migrations 014 and 015 are additive: 014 adds nullable `niche_id`, its composite FK, indexes and a trigger scoped to Model 2 schedule rows; 015 adds the append-only scheduler reconciliation audit table and immutability trigger. Disposable CI applied all 16 numbered migrations from a clean PostgreSQL 16 database. This is not a rehearsal against a sanitized production-like snapshot.

Proposed release procedure (not executed):
1. Capture and verify a restorable backup/snapshot using the approved database operations process.
2. Rehearse migrations 014 and 015 against a sanitized clone with production-like schema, representative legacy schedules/jobs and audit-table constraints.
3. Verify legacy schedules retain `niche_id IS NULL`, remain readable/updatable under legacy behavior, and no existing rows are backfilled or rewritten.
4. Verify Model 2 constraints, indexes and trigger; run read-only post-migration integrity checks.
5. Deploy application code only after migration rehearsal and explicit approval.
6. Rollback application code first if required; leave the additive schema in place. Do not drop migration 014 objects if Model 2 schedule rows may exist. Schema rollback requires a separately designed data-preserving procedure.

No production/shared DB migration or backup operation was performed.

### R4 — Shared API key is service authentication, not human identity

**Severity:** Medium — accepted architecture constraint.

Model 2 registry/learning and scheduler routes use the existing fail-closed service API key. The system is intentionally one owner/operator, not a multi-tenant identity platform. The key must be protected as a high-privilege service credential, and logs/UI must not expose it. Do not claim human actor attribution or tenant isolation.

### R5 — Scheduler timing is best-effort

**Severity:** Medium — operational constraint.

The worker workflow is hourly and GitHub Actions cron may be delayed. It processes at most one due job per invocation. This is not a precise real-time scheduler. Release materials must communicate best-effort timing and ensure backlog behavior/rate limits are acceptable before activation.

### R6 — Non-blocking CI maintenance warnings

**Severity:** Low.

Current CI emits a Starlette/httpx TestClient deprecation warning and GitHub Actions Node.js 20 / `ubuntu-latest` migration warnings. They did not fail CI. Track dependency/action updates separately; do not change dependencies solely to silence warnings without compatibility tests.

## 4. Migration compatibility / rollback assessment

- Migration 014 adds a nullable column, FK, check, indexes and trigger; migration 015 adds an audit table, constraints and append-only trigger. Neither migration rebuilds existing tables or backfills existing business rows.
- Existing Model 1 schedules keep `niche_id NULL`; trigger logic explicitly skips legacy rows.
- Existing one-active-schedule-per-account unique index is retained.
- Application rollback can leave the additive schema installed; old code does not need to read `niche_id` to use its existing explicit-column queries.
- Dropping either migration is not an approved rollback strategy. If Model 2 schedule or reconciliation audit rows exist, dropping constraints, triggers, tables or columns risks losing or invalidating state.
- Production-like migration rehearsal and restore test remain unverified.

## 5. Release scorecard

| Area | Assessment | Evidence / gap |
|---|---|---|
| Account isolation | Pass in tests | Exact account+niche composite FK and repository/workflow checks |
| Authentication | Pass for service-key model | Fail-closed shared API key; no human/tenant identity |
| Publication safety | Pass on feature branch / production conditional | Single gateway, idempotency, uncertainty quarantine, atomic operator reconciliation and append-only audit; no live publication test |
| Quota concurrency | Pass in CI | Same-account serialization; different-account parallel claims; ambiguous outcomes remain quota-consuming; definite pre-publish conflicts do not (exact-head CI run 42845977735) |
| Legacy compatibility | Pass in CI | Nullable niche, unchanged legacy branch, regression suite |
| Migration integrity | Pass in disposable CI | All 16 migrations applied; production-like rehearsal not run |
| Rollback | Partial | App rollback can retain additive schema; data-preserving schema rollback/restore not rehearsed |
| Operations | Conditional | Hourly best-effort worker can publish; explicit enablement/runbook needed |
| Observability | Partial | Read-only job/ledger inspection and audit are available; alerting policy still needs definition |
| Deployment | Not approved | No PR, merge, production migration or deployment authorized |

## 6. Exit criteria before any release approval

- [x] Exact-head CI passes after R1 hardening; migration ledger and fixture cleanup verified (run `42536949741`).
- [x] Operator reconciliation procedure for uncertain scheduler jobs is documented and tested without a real Pin write (run `42538656224`).
- [ ] Production-like sanitized migration rehearsal and restore/rollback rehearsal pass.
- [ ] Owner reviews the scheduled worker's production side effects and explicitly approves activation window/controls.
- [ ] Security review confirms service key handling, account scoping, log redaction and operational access.
- [ ] Owner explicitly approves production migration, deployment, and any scheduler activation as separate actions.

**Phase 10 status remains PRE-RELEASE / BLOCKED.** Passing disposable CI is not production readiness, migration approval, deployment approval or authorization to publish Pins.


### Phase 10 — Security review follow-up (2026-11-09)

- Reconciliation audit immutability now covers row-level UPDATE/DELETE and statement-level TRUNCATE through database triggers. CI fixture teardown uses scoped DELETE rather than bypassing the trigger with TRUNCATE; a PostgreSQL regression test verifies TRUNCATE is rejected and the audit row remains.
- Authentication remains shared service-key authentication. It does not identify a human operator or provide per-person authorization/non-repudiation. The audit's free-text evidence is operator-supplied and must not contain credentials or sensitive personal data. A future per-operator identity model requires a real authenticated principal, not a caller-controlled identity header.
- Database owners/superusers can disable/drop triggers or otherwise alter the audit table; append-only triggers protect against ordinary application SQL, not privileged DBA tampering.


### Synthetic populated legacy upgrade rehearsal — added 2026-11-09

A new disposable-CI test applies migrations 001–013, inserts synthetic legacy Model 1 scheduler data, and then applies migrations 014–015 to verify preservation of legacy schedule/job state and update semantics. This is a synthetic compatibility test only; it is not evidence from a sanitized production snapshot and does not satisfy the production-like backup/restore rehearsal requirement.

- [x] Synthetic populated legacy upgrade rehearsal passed in CI run `42540730785` (236 passed). This does not replace the sanitized production-like snapshot and restore/rollback rehearsal.


### Workflow provider-error redaction — verified in disposable CI (2026-11-09)

- Removed raw image/content provider exception messages from end-to-end workflow logs; image-generation API responses now return a fixed generic error instead of raw provider exception text.
- Added regression tests with synthetic secret markers proving that neither image nor content provider exception text appears in HTTP responses or application logs.
- Exact-head CI run 42545788592 passed on cfc7f96956a0ebf69e978eaf4e504f7de69994c0; all workflow steps, migration ledger/fixture cleanup checks and PostgreSQL container teardown passed.
- Targeted review found DeepSeek logs bounded response metadata only and Cloudflare logs provider status/codes only. This does not constitute exhaustive Git-history secret scanning or a production log-retention/access-control audit. Secret rotation and operational access review remain outstanding release gates.
- No production DB access, provider write, scheduler activation, deployment, Pin or Board creation occurred.


### Credential/account identity review — implementation committed, CI pending (2026-11-09)

**Status:** Partial security hardening; release gate remains open.

- Credential writes now reject `account_id` values that do not exactly match `pinterest:<pinterest_user_id>` before encryption/database access. Access-token and refresh-token reads repeat the same metadata validation before decrypting.
- The Hub Pinterest operation endpoint performs a read-only `GET /user_account` preflight and compares the returned Pinterest user ID to stored metadata before executing any requested operation, including `create_board`. Identity mismatch returns conflict before the write request.
- Synthetic regression tests cover mismatched ingest metadata, malformed stored metadata, and a real-token identity mismatch with an assertion that no board-create request is issued. Both test files are included in the explicit CI test list.
- **CI for these latest commits is not yet verified.** The prior successful exact-head run `42545907875` predates this patch and does not cover it.
- Shared `X-API-Key` and `X-Credential-Ingest-Key` remain service-level credentials, not per-human identity, per-user permissions, or tenant isolation. This is acceptable only under the explicitly documented single-owner operating model.
- **Open high-priority credential lifecycle gap:** the vault has one active `PINTEREST_TOKEN_ENCRYPTION_KEY`, no persisted key ID/key ring, and no tested re-encryption/rotation procedure. A direct environment-key replacement can render existing access/refresh ciphertext undecryptable. Keep the current key stable until versioned key management and a rollback-tested re-encryption procedure are implemented.
- No production credentials/database, Pinterest OAuth refresh, Board/Pin creation, scheduler execution, deployment, PR, or merge occurred.


### Versioned credential encryption and controlled rotation — implementation committed, CI pending (2026-11-09)

- Optional key ring: `PINTEREST_TOKEN_ENCRYPTION_KEYS` JSON object maps key IDs to base64-encoded 32-byte keys; `PINTEREST_TOKEN_ENCRYPTION_ACTIVE_KEY_ID` selects the write key. The existing single-key `PINTEREST_TOKEN_ENCRYPTION_KEY` remains supported for legacy deployments.
- New AES-256-GCM ciphertext is versioned and includes a key ID. Existing nonce-prefixed legacy ciphertext remains readable when the original key is retained. AAD continues to bind each token to its account and token type.
- Added operator-only per-account `reencrypt_pinterest_credential(account_id)`, which re-encrypts access and refresh ciphertext in one row transaction without calling Pinterest. It is not exposed through HTTP.
- Synthetic tests cover legacy compatibility, key-ID selection, active-key changes while old keys remain retained, wrong-key rejection, malformed configuration, and re-encryption. The explicit CI workflow includes the new test module, but **the latest change set is still awaiting independently verified CI**.
- Rotation is **not executed**. Required order: restorable backup; configure old key under `legacy` plus new active key; deploy only with separate approval; re-encrypt every credential row; verify all envelopes and decryptability; retain old key through rollback window; remove old key only after rollback/restore evidence. Never remove the old key while any ciphertext still references it.
- No production database or secrets were accessed or changed. No live OAuth, Pinterest write, Pin/Board, scheduler, deployment, PR or merge occurred.


### Security follow-up — keyring and canonical ingest auth CI PASS (2026-11-09)

- **Exact-head CI PASS:** run `42549027659`, commit `0b621fd7a133d8809123917b5365199c0893bd8d`. All steps passed, including the isolated disposable database guard, static/PostgreSQL tests, complete migration-ledger and fixture-cleanup checks, and container teardown.
- Added versioned AES-256-GCM ciphertext envelopes with key IDs, optional JSON key ring and active key ID settings, legacy ciphertext compatibility, and a per-account operator-only re-encryption primitive. Synthetic tests cover key selection, retained old-key reads, wrong/missing keys, legacy reads and re-encryption.
- Canonicalized trusted-Hub credential-ingest authentication in `app/auth.py`. Pinterest Trends now uses the same fail-closed guard as main integration routes: missing configuration is 503; invalid supplied key is 401.
- Credential disconnect now rejects invalid stored account identity safely. Account-operation preflight checks actual Pinterest identity before any requested write.
- This CI run uses disposable synthetic PostgreSQL and mocked provider responses. It is not evidence of production key rotation, complete credential inventory migration, sanitized production backup/restore, or live account verification.
- **Production key rotation remains NOT DONE.** Required steps: retain original key under `legacy`; configure new active key; separately approve deployment; re-encrypt every credential row including revoked rows with ciphertext; verify key IDs and decryption; retain old key through rollback; remove it only after backup/restore and rollback evidence. Do not change or remove the current production key before those steps.
- No production database/secret, Pinterest write, OAuth refresh, scheduler activation, Pin/Board creation, deployment, PR or merge occurred.



### Disposable PostgreSQL backup/restore rehearsal — CI PASS (2026-11-09)

- Added a synthetic custom-format backup/restore regression on the isolated GitHub Actions PostgreSQL 16 service. It applies all 16 numbered migrations, inserts representative legacy Model 1 schedule/source/job rows, creates a `pg_dump --format=custom` archive using PostgreSQL 16 client tools, restores into a separate empty database using `pg_restore`, and verifies migration ledger, legacy row preservation, nullable `niche_id`, and migration trigger presence.
- Exact-head CI run `42594318912`, commit `b38e66180a336d04e61f5439ea05e7c1d61c5981`: **265 passed, 0 failed, 1 warning**. Full migration ledger check confirmed all 16 migrations; fixture cleanup passed; PostgreSQL service teardown passed.
- The initial restore attempt exposed a client/server major-version mismatch (PostgreSQL 18 client against PostgreSQL 16 server). The final test runs `pg_dump` and `pg_restore` from the same `postgres:16` container image as the disposable server; the final CI run passed.
- **Scope limitation:** this is a synthetic disposable-database backup/restore rehearsal, not a sanitized production-like snapshot. It does not validate production data volume, provider secrets, Neon backup/PITR configuration, production credentials, or real operational restore access. The production-like snapshot rehearsal and owner-approved operational restore/rollback plan remain open release gates.
- No Neon/production database, production secret, live OAuth, Pinterest API write, scheduled worker, real Pin/Board, PR, merge or deployment was used or authorized.


### Credential key-usage inventory — implementation and CI verified (2026-11-09)

- Added read-only operator maintenance primitive `pinterest_credential_encryption_inventory()`. It inspects every credential row regardless of connected/revoked status and reports aggregate access/refresh ciphertext counts by key ID, legacy format, absent refresh ciphertext, malformed envelope and invalid canonical account metadata.
- The inventory never decrypts token material, returns account identifiers, or calls Pinterest. It is not exposed as an HTTP route.
- Synthetic regression verifies revoked rows are included, malformed identity/envelope states are counted, and the decrypt function is never invoked.
- Exact-head CI run `42594679834`, commit `8738194e9715278f835da665b6a58348ccaa7086`: **266 passed, 0 failed, 1 warning**. All 16 migrations, fixture cleanup and PostgreSQL teardown passed.
- This makes a future operator-led rotation easier to reconcile, but does not perform batch re-encryption or prove production key coverage. Production key rotation remains NOT DONE; backup/restore against a sanitized production-like snapshot remains open.



### Current verified security and recovery status — supersedes earlier pending notes (2026-11-09)

- Versioned AES-256-GCM credential keyring, legacy ciphertext compatibility, per-account re-encryption primitive, canonical Pinterest identity checks, and read-only aggregate credential key inventory are implemented on the feature branch.
- Connected-state preflight now verifies the stored `account_id` exactly matches `pinterest:<pinterest_user_id>`; Model 2 schedule creation/activation/worker preflight rejects a connected row with mismatched identity without reading or decrypting token bytes.
- Publication reservation now follows account/profile → niche → assignment → credential metadata → publication advisory lock → publication row. An attributed retry requires the exact explicit niche context. This removes the previously identified inverse lock-order path against scheduler reconciliation.
- Synthetic PostgreSQL CI exact-head run `42611158364`, commit `739b1ae70d3b7a3b01ac7644a34f14f235ab0ecc`: **269 passed, 0 failed, 1 warning**. All 16 migrations recorded; fixture cleanup and PostgreSQL teardown passed.
- Synthetic custom-format PostgreSQL 16 backup/restore rehearsal separately passed in run `42594318912` (**265 passed** at that checkpoint). It verifies legacy rows/schema and triggers after restore into a second disposable database.
- These are CI/synthetic results only. Production key rotation, complete production credential re-encryption, sanitized production-like snapshot restore, Neon PITR/backup configuration, owner-operated restore/rollback rehearsal and production access review remain **NOT DONE**.
- The branch remains unmerged and undeployed. No production DB or secrets were accessed/changed; no live OAuth refresh, scheduler activation, real Pin/Board creation, PR or merge occurred.



### Scheduler lock-order hardening and default-branch cron risk (2026-11-09)

- Worker stale-claim quarantine and post-workflow job finalization now follow account profile → niche → assignment → schedule → job lock order, matching scheduler reconciliation. Stale claims are handled one at a time in a separate transaction; worker finalization rechecks the job is still processing before updating it.
- Added explicit lock-order regression tests. Exact-head CI run `42611981311`, commit `3562ef346ec03e6b31815aef4dfb1b9f3c2f0cfe`: **274 passed, 0 failed, 1 warning**. All 16 migrations, fixture cleanup and PostgreSQL teardown passed.
- **Operational blocker discovered:** read-only GitHub Actions history shows that default-branch `main` has active scheduled triggers for both Affiliate Scheduler Worker and Pinterest Learning Loop. This supersedes prior release-readiness wording that implied no live scheduled execution had occurred.
- Affiliate Scheduler Worker run `42581914921` called the Render production `/affiliate-scheduler/run-due` endpoint and reported `claimed=true`, `processed=true`, `job_id=13`, `status=succeeded`. Its wrapper omits `published` and Pin ID, so whether a new Pin was created is **unknown from this evidence**.
- Pinterest Learning Loop run `42611471024` called the Render production `/learning-loop/run` endpoint and reported `ok=false`, 17 Pins checked, 16 analytics snapshots saved, descriptive evaluation only, and `model_trained=false`. This confirms live analytics ingestion/snapshot writes, not Pin publishing.
- The assistant did not dispatch these runs and did not change or disable workflows on `main`. The feature branch remains unmerged and undeployed.
- **Release gate:** owner must explicitly decide whether the main-branch cron workflows should be disabled until go-live approval. Do not merge/deploy this feature branch or enable/dispatch any worker without separate approval. If the owner wants to confirm job 13's publication outcome, authorize a narrowly scoped read-only production ledger/log inspection; do not query production data without that approval.


### Follow-up read-only Pinterest verification hardening (2026-11-09)

- Added bounded GET-only Board enumeration and exact-name Board resolution; missing/duplicate names, invalid/repeated pagination cursors, provider errors and incomplete pagination fail closed. No Board creation.
- Existing publication verification now uses a credential reader that refuses expired/unknown-expiry tokens instead of silently refreshing OAuth.
- These are read-only verification safeguards. The feature branch's existing atomic scheduler reconciliation endpoint and runbook remain the authoritative recovery path. Exact-head tests and PostgreSQL CI must be rerun after this follow-up.
- Latest-base local suite after this follow-up: **336 passed, 74 skipped, 1 non-blocking warning**. PostgreSQL backup/restore and populated legacy-upgrade modules require disposable PostgreSQL and were not run locally; exact-head CI is still required.

### Exact-head CI for read-only verification hardening — PASS (2026-11-09)

- Commit `9a5c6f056f17449f6111b1d6e098775cfa363fa3`, GitHub Actions run `42644496929`: **320 passed, 0 failed, 1 non-blocking warning** on disposable PostgreSQL 16.
- The run applied and recorded all 16 numbered migrations, verified cleanup of synthetic Model 2 and Model 1 fixtures, and stopped the PostgreSQL service.
- The CI run covers the new bounded GET-only Board listing/resolution tests, no-refresh credential tests, the connection-scoped publication reconciliation helper tests, the existing atomic scheduler reconciliation tests and the manual-publish auth fixture correction.
- This is isolated CI evidence only. It does not verify live Pinterest credentials or Board/Pin state, production database operations, production cron control, deployment or scheduler activation.


### Latest exact-head continuation verification — 2026-11-09 (authoritative)

This section supersedes earlier notes in this document that say the read-only Board resolver/no-refresh credential follow-up still awaits CI, or that identify `9a5c6f0` as the latest verified feature-branch head.

- Feature branch exact HEAD: `369239ec8e5ed7a7fadcd39cc86a041f8dd98bef`; working tree clean at verification; 155 commits ahead of `origin/main`, 0 behind.
- Exact-head GitHub Actions run `42644694242`: **320 passed, 0 failed, 1 non-blocking Starlette/httpx warning**. The run includes the bounded GET-only Board resolver, no-refresh credential reader, connection-scoped reconciliation helper, atomic scheduler reconciliation, credential keyring/identity controls and scheduler lock-order regression suite.
- CI verified a loopback-only disposable PostgreSQL 16 target, empty `DATABASE_URL`, all 16 numbered migration records, cleanup of Model 2 and synthetic Model 1 fixtures, and PostgreSQL service teardown.
- Local full suite without `TEST_DATABASE_URL` was not a valid full DB integration run: two tests (`test_model2_backup_restore.py` and `test_model2_legacy_upgrade.py`) correctly failed their explicit guard requiring `TEST_DATABASE_URL` rather than falling back to `DATABASE_URL`. With those two PostgreSQL-admin integration modules excluded, local result was **336 passed, 74 skipped, 1 warning**. Both DB integration modules were included in and passed by exact-head disposable PostgreSQL CI.
- Local `compileall` and `git diff --check` passed. No new implementation was needed in this continuation because the previously implemented feature set was already present and exact-head CI verified it; no duplicate components were added.
- **Release status remains PRE-RELEASE / BLOCKED.** The following are not solvable by another local code/test run and remain operational/owner gates: sanitized production-like snapshot migration plus restore/rollback rehearsal; Neon backup/PITR and owner-operated restore verification; production credential inventory and explicitly approved key rotation/re-encryption; production access and log-retention review; owner decision on existing main-branch scheduled worker/Learning Loop behavior; separate approvals for production migration, deployment and scheduler activation.
- No production DB write/read, secret access or rotation, OAuth refresh, Pinterest write, real Pin/Board creation, scheduler dispatch, PR, merge or deployment occurred in this continuation.


## Phase 10 — Master blocker checklist and one-by-one execution plan (2026-11-09)

This checklist is the active execution tracker. Do not repeat completed synthetic work. Close each gate only with recorded evidence.

### Gate 1 — Migration, backup and restore safety
- [x] Disposable PostgreSQL 16 custom-format `pg_dump` / `pg_restore` rehearsal; all 16 migrations, legacy rows and required triggers verified. CI run `42594318912` (265 passed).
- [x] Populated legacy Model 1 upgrade through migrations 014–015 verified in disposable CI; CI run `42540730785`.
- [ ] Sanitized production-like snapshot migration and restore/rollback rehearsal. **Blocked:** requires an owner-approved sanitized snapshot and approved isolated target. No production DB access or snapshot extraction is authorized by this checklist.
- [ ] Document and verify the application rollback / additive-schema retention procedure against that sanitized clone. Do not drop migrations 014/015 as a rollback shortcut.

### Gate 2 — Neon backup / PITR and restore access
- [x] Record Neon project's backup/PITR availability, retention and recovery-point capabilities from the approved read-only project-settings inspection (2026-11-10; evidence below).
- [ ] Verify the owner/operator can initiate and complete a restore into an isolated target, without overwriting production.
- [ ] Record restore owner, escalation path, expected recovery-point objective (RPO) and recovery-time objective (RTO). Do not invent values; owner must approve targets.
- **Boundary:** no production Neon inspection, restore, branch mutation or database write without separate explicit approval.

### Gate 3 — Credential inventory and controlled key rotation
- [x] Versioned AES-256-GCM keyring, legacy ciphertext reader, key-ID inventory and one-account re-encryption primitive implemented and covered by synthetic tests.
- [ ] Obtain owner-authorized production aggregate key inventory (no token values, plaintext, account identifiers or secrets in reports).
- [ ] Confirm a restorable backup and old-key retention before any rotation.
- [ ] Obtain explicit approval for keyring configuration/deployment and batch re-encryption.
- [ ] Re-encrypt and verify every eligible credential row, including revoked rows that still contain ciphertext; retain old keys through the rollback window.
- **Boundary:** no production secret access, key generation, environment change, token decryption, OAuth refresh or rotation until separately approved.

### Gate 4 — Production access, logging and retention security
- [x] Complete static application-code review of authentication, authorization boundaries, account scoping, secret redaction and error handling (2026-11-10; evidence below).
- [ ] Obtain owner-authorized evidence for production service access, database roles, log access, retention and deletion policy.
- [x] Record findings and remediate code-owned issues on this feature branch; static review found no additional code-owned fix required (2026-11-10). Production configuration changes require separate approval.

### Gate 5 — Existing scheduled side effects
- [ ] Owner decides whether the already-scheduled `main` Affiliate Scheduler Worker may continue to execute jobs before Model 2 go-live.
- [ ] Owner separately decides whether the `main` Pinterest Learning Loop may continue analytics snapshot writes.
- [ ] Document allowed activation window, backlog handling, rate limits, monitoring and stop procedure.
- **Boundary:** do not dispatch, pause, resume, edit or activate production workflows without explicit approval.

### Gate 6 — Release authorization
- [ ] Owner approves production migration as a separate action.
- [ ] Owner approves application deployment/merge as a separate action.
- [ ] Owner approves scheduler activation as a separate action.
- [ ] Final release review confirms all prior gates and evidence links.

### Execution rule
Work in gate order. For each gate: inspect existing evidence first; implement only missing code/documentation that is safe on the isolated feature branch; run targeted tests and exact-head CI where code changes; update this tracker with evidence; then move to the next gate. If a gate requires owner credentials, production access, a sanitized snapshot, or a business decision, mark it BLOCKED with the exact required owner action rather than bypassing the control.

**Current release state: PRE-RELEASE / BLOCKED.** No production DB writes, production secret changes, OAuth refresh, Pinterest API writes, real Pin/Board creation, scheduler changes, merge or deployment are authorized by this checklist.


### Gate 4 execution note — duplicate trusted-Hub auth guard corrected (2026-11-09)

- Static review found `POST /trend-visuals/run` used a local duplicate `X-Credential-Ingest-Key` guard. Unlike the canonical shared guard, it returned HTTP 401 when the credential-ingest key was not configured (the shared fail-closed contract is HTTP 503 for missing server configuration and 401 for an invalid supplied key).
- Corrected `app/trend_visuals.py` to depend on `app.auth.require_credential_ingest_key`; removed the duplicate local guard.
- Added regression tests for unconfigured key (503), wrong key (401), and valid key (handler invoked). Targeted test result: `6 passed, 1 existing Starlette/httpx deprecation warning` via `pytest -q tests/test_trend_ingest_auth.py`.
- This was initially recorded as awaiting CI. It is now covered by exact-head disposable PostgreSQL CI run `42731241964` on commit `a4f9c3aafeb67035d4c264cbb3db62e263e372be`: **323 passed, 0 failed, 1 non-blocking Starlette/httpx warning**. All 16 numbered migrations were recorded, synthetic fixtures were cleaned, and the PostgreSQL 16 service was stopped. The run included `tests/test_trend_ingest_auth.py` and the backup/restore and legacy-upgrade integration modules. Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42731241964.
- No database, production secret, OAuth, Pinterest API write, Pin/Board, scheduler, deployment, PR or merge was used.


- After the trusted-Hub guard correction, the broader local suite (excluding only the two PostgreSQL-admin integration modules that require a dedicated `TEST_DATABASE_URL`) passed: **339 passed, 74 skipped, 1 non-blocking warning** in 23.89s. `compileall` and `git diff --check` also passed.
- The two excluded backup/restore and legacy-upgrade modules remain covered by their prior disposable PostgreSQL CI evidence; they were not rerun locally without the isolated database service.
- The change is still uncommitted and unpushed. Exact-head GitHub Actions must verify it before this correction can be marked CI-closed.


### Gate 4 execution note — application-level security review checkpoint (2026-11-09)

- Reviewed route authentication boundaries across Model 2 registry/learning, scheduler, trends ingestion, manual publishing, Pinterest account operations, dashboard and publication verification.
- Model 2 registry and learning routers apply the shared fail-closed `X-API-Key` dependency at router level. Scheduler endpoints declare the shared API-key guard. Trends and trusted-Hub credential endpoints use the shared credential-ingest guard. Manual Pin publishing uses the credential-ingest guard as a function dependency. Dashboard data endpoints require the signed session; the cookie is Secure, HttpOnly and SameSite=Strict.
- Dashboard HTML and session create/delete routes are intentionally reachable without an existing session; data endpoints are not. Health is public by design; readiness and provider diagnostics require the API key.
- **Authorization model limitation confirmed:** the shared service API key is a single-owner operator boundary, not per-human RBAC or independent tenant identity. Model 2 account scoping is enforced in domain/repository operations, but production multi-user exposure is not approved by this baseline. Do not describe this as multi-user authorization.
- Reviewed the manual publishing preflight and operation boundary: manual publishing checks stored Pinterest identity and board ownership before publication reservation/write; the general account operation endpoint checks live Pinterest identity before its allowlisted operation. No live request was sent during this review.
- Dashboard database exceptions return a generic 503; the read-only Pinterest verification client raises bounded/sanitized `PinterestReadError` messages. No raw provider response body or bearer token is intentionally returned by these inspected paths.
- Targeted security regression set: **102 passed, 1 existing Starlette/httpx deprecation warning** (dashboard, Model 2 APIs, credential vault/keyring, account identity, manual publishing, reconciliation and authentication modules).
- Broader local suite after the shared guard correction: **339 passed, 74 skipped, 1 warning**; `compileall` and `git diff --check` passed.
- Remaining Gate 4 items are operational: production database/service roles, human access review, log-reader permissions, retention/deletion policy and production configuration evidence. These require owner-authorized production evidence and are not marked complete.
- Exact-head CI has not been rerun after the shared guard correction. The feature branch remains uncommitted/unpushed; no deployment, production credential, production database, OAuth refresh, scheduler change, Pin or Board operation occurred.


### Gate 4 execution note — runtime route authorization inventory (2026-11-09)

- Re-enumerated FastAPI route declarations across `app/` and inspected the assembled application route table. Router inclusion is lazy in the installed FastAPI version, so the assembled table exposes `_IncludedRouter` placeholders; the source router declarations were therefore also inspected directly.
- Operational/data-changing route groups are protected by the shared API-key or credential-ingest dependency: Model 2 registry and learning routers (router-level), affiliate scheduler operations, workflow, diagnostics, Learning Loop, trends/trend-visuals ingestion, Pinterest credential/analytics/refresh/operation endpoints, manual publishing, product/content writes, and publication reconciliation/publishing.
- Dashboard data endpoints call the signed-session validator. The dashboard HTML is intentionally public; session creation verifies the submitted API key and issues a Secure, HttpOnly, SameSite=Strict cookie; session deletion only clears that cookie and does not expose data or perform an operational mutation.
- `/health` is intentionally public. FastAPI schema/docs routes are enabled by framework defaults; they expose API descriptions, not an authorization bypass. Whether to disable or protect documentation endpoints in production is an owner deployment-policy decision and should be recorded before public exposure if API surface concealment is required.
- No confirmed unauthenticated publishing, scheduler, credential, analytics-ingestion, registry-write or learning-write route was found in this pass. This is static/code-level route evidence, not proof of production gateway, reverse-proxy or identity-provider configuration.
- Gate 4 remains open for production role/access evidence, log-reader permissions, retention/deletion policy, and owner confirmation of acceptable documentation exposure. The existing shared API key remains a single-owner operator boundary, not multi-user RBAC.


### Additional release blocker — GitHub main-branch protection (owner/admin action)

- Previous read-only GitHub repository audit found `main` branch protection disabled, required-status-check enforcement off, and no repository rulesets (`GET /branches/main` / `GET /rulesets`).
- This is a release-control gap: a green CI run alone does not prevent an unreviewed or failing-status merge to `main` while protection is disabled.
- Required owner/admin action before production release: enable branch protection or an equivalent ruleset for `main`, require the relevant CI status check(s), prevent force-push and branch deletion, and verify the effective settings with a fresh read-only check.
- No repository settings were changed in this continuation. Do not treat the feature branch's successful CI as proof that `main` is protected.


### Trusted-Hub trend-ingest guard — exact-head CI closure (2026-11-10)

- Commit `a4f9c3aafeb67035d4c264cbb3db62e263e372be` uses the canonical fail-closed `require_credential_ingest_key` dependency for `/trend-visuals/run`; the duplicate local guard is removed.
- Exact-head GitHub Actions run `42731241964`: **323 passed, 0 failed, 1 non-blocking warning** on isolated PostgreSQL 16.15. All 16 migrations recorded, synthetic Model 1/Model 2 fixture cleanup passed, and PostgreSQL service teardown passed.
- No production DB, credential, Pinterest write, real Pin/Board, scheduler activation, deployment, PR or merge was used.


### Backup repository main-branch restore rehearsal — PASS (2026-11-10)

- After PR #2 was merged, manually dispatched `Neon backup restore rehearsal` from backup repository `main` at commit `836a5cdc7a178483d16d56b8a8d52dfa16c0e2c4`.
- GitHub Actions run `42731539863`: **success**. It selected `backup-20261109-085701-42589610843` by release `publishedAt`, verified the encrypted asset checksum, decrypted the GPG archive, and restored it with PostgreSQL 16 `pg_restore` into an isolated ephemeral PostgreSQL 16 service.
- Restore verified **12 base tables**, removed temporary restore files and stopped the PostgreSQL service. No Neon production database was restored, overwritten or written.
- This closes the merged-main encrypted-backup restore rehearsal for the current backup format. It does **not** satisfy the separate sanitized production-like Model 2 snapshot rehearsal or prove an operator can restore a Neon branch/root database.
- Run: https://github.com/shehrozali6465372-ctrl/pinterest-agent-database-backups/actions/runs/42731539863

### Neon Free recovery configuration — read-only evidence (2026-11-10)

- Owner-authorized read-only project settings inspection confirmed Neon plan `free_v3`, production branch `main`, and a **6-hour PITR history window**.
- No automatic snapshot schedule is configured; automatic snapshots are not available on the Free plan. One manual snapshot was listed: `production-main-pre-restore-rehearsal-20261103`.
- No SQL was run; no branch was created; no restore, database write or setting change occurred. Neon remains on Free; no paid upgrade is proposed.
- The successful GitHub Actions restore above proves encrypted backup recovery into isolated PostgreSQL, not Neon PITR restore access. Owner-operated Neon restore rehearsal, RPO/RTO targets and escalation ownership remain open.

### GitHub repository merge protection — owner policy gate

- Read-only GitHub checks confirm the agent repository `main` branch has no branch protection and no repository rulesets. The authenticated account has repository admin permission, but no settings were changed.
- The private backup repository's branch-protection/ruleset API reports that the feature requires GitHub Pro or a public repository. Do not make the private backup repository public or upgrade a plan without owner direction.
- Required owner decision: choose an acceptable merge-control strategy for the private repositories and plan constraints. Until then, green CI does not equal enforced protection against unreviewed or failing-status merges.


### Gate 4 execution note — static application security review closed (2026-11-10)

- Rechecked the shared fail-closed API-key and credential-ingest guards, Model 2 registry/learning router dependencies, account/niche-scoped repository and learning SQL predicates, Pinterest identity preflight, and protected operational route groups. No new application-code authorization bypass was identified in the inspected paths.
- Confirmed the approved operating model is one owner/operator managing multiple Pinterest accounts. The shared `X-API-Key` is service authentication, not per-human RBAC or tenant identity; no human/tenant identity is fabricated. This remains acceptable only for the explicitly selected single-operator deployment model.
- Rechecked application logging and broad exception boundaries. Inspected content, media and workflow logs use bounded stage/status/exception-type metadata rather than raw provider exception text; inspected API error paths return generic storage/provider failures where appropriate. This is not a full historical log scan or proof of production log access/retention controls.
- Reconfirmed account/niche data operations use canonical account IDs and explicit account+niche predicates; learning projections join analytics to succeeded publications and exact account/niche attribution. Existing CI covers the cross-account and identity regressions.
- Latest exact-head feature CI remains run `42731770533` at `1e03f196a0380c88aebe2a0b1bb3272273dc6873`: **323 passed, 0 failed, 1 non-blocking warning**, all 16 migrations recorded, fixtures cleaned and disposable PostgreSQL 16 stopped. No source code changed during this review.
- **Gate 4 static application-code item is closed.** Remaining Gate 4 production evidence is still open: production service/database roles, human access, log-reader permissions, retention and deletion policy. No production settings or logs were accessed or changed in this review.
- No production DB access/write, secret access/rotation, OAuth refresh, scheduler operation, Pinterest API write, Pin/Board creation, PR, merge or deployment occurred.


### Gate 2 and Gate 4 evidence update — read-only Neon recovery settings (2026-11-10)

- Read-only Neon project settings inspection confirmed plan `free_v3` (Free), 6-hour PITR history, no automatic snapshot schedule (not available on Free), and one listed manual snapshot `production-main-pre-restore-rehearsal-20261103`. No SQL, branch creation, restore, configuration change or production data access occurred during that settings inspection.
- The separate private GitHub backup repository's merged-main restore rehearsal passed in run `42731539863`: checksum verification, GPG decryption and PostgreSQL 16 restore into an isolated disposable container; 12 base tables verified. This is independent backup evidence, not a Neon restore.
- Gate 2's capability-inventory item is closed. Owner/operator restore execution into an isolated Neon target, restore access/permissions, escalation path and owner-approved RPO/RTO remain open. Keep Neon Free; do not add an automatic-snapshot schedule or upgrade the plan.
- Gate 4's code-owned remediation item is closed: the static application review found no additional code-owned fix required. Production service/database roles, human access, log-reader permissions, retention and deletion evidence remain open.
- No production DB writes, restore, branch mutation, secret access/rotation, scheduler change, Pinterest write, deployment or merge occurred.

### 2026-11-10 continuation — live runtime, scheduled side effects and backup snapshot classification

- Confirmed the deployed Render service is pinterest-affiliate-marketing-agent, Free plan, one configured instance, auto-deploy from main; latest live deploy dep-dboumq3m5ojs738e1if0 runs Model 1 commit 2fd07669d19e68d73099c9e3f589e2db8ca87078. Model 2 feature code remains on the isolated feature branch and is not deployed.
- Read-only runtime checks from the connected device: GET /health returned HTTP 200; GET /openapi.json returned HTTP 200. / and /ready returned HTTP 404; no readiness route is defined in this deployed Model 1 API. Render logs for 00:00–01:30 UTC contained no application ERROR/WARNING entries and no HTTP 5xx request logs. HTTP request/latency metrics were unavailable in the queried interval; no performance pass is claimed.
- A second default-branch Affiliate Scheduler Worker run 42726032661 at 00:08:50 UTC on main commit 2fd07669... completed successfully. The safe workflow output was claimed=true, processed=true, job_id=14, status=succeeded. The current scheduler handler returns published and already_published, but the existing workflow output projection omits both. Therefore whether job 14 created a new Pin or observed an already-published result remains UNKNOWN. No manual worker dispatch was issued in this continuation.
- The scheduled Pinterest Learning Loop run 42611471024 remains a confirmed partial production operation: 17 Pins checked, 16 analytics snapshots saved, ok=false, descriptive evaluation only, model_trained=false. It performed live Pinterest analytics GETs and wrote 16 analytics snapshots to the production database; the failed Pin's safe failure stage was not included in the workflow summary.
- Feature-branch-only observability remediation: added scripts/workflow_summary.py and behavioral tests to include scheduler published/already_published booleans, plus Learning Loop failure counts/stage/status aggregates, while excluding Pin IDs, affiliate URLs, per-Pin payloads and credentials. Missing pin_results remains unknown (null), not fabricated zero. Both existing workflow YAML files call the shared helper after checkout. Targeted tests: 5 passed; both workflow YAML files parsed and helper wiring was verified. Exact-head CI closure is recorded in the final section below. This does not alter provider calls, scheduling cadence, job selection or publication behavior, and is not live on Render/main.
- The local unencrypted PostgreSQL custom-format dump pinterest_affiliate_20261103.dump was classified using archive metadata and schema-only extraction. Its archive lists 8 base tables and TABLE DATA entries, including pinterest_credentials. Schema-only extraction confirmed access_token_ciphertext and refresh_token_ciphertext bytea columns. No TABLE DATA was extracted or restored, and no row values were read, queried or copied. The dump has no scheduler/Model 2 tables. Treat it as sensitive: it is an older Model 1 dump, is not a sanitized production-like snapshot, and cannot prove migrations 014/015. Do not use it for the Model 2 restore rehearsal.
- Sitelemetry's public-only security scan was partial: DNS and TLS checks passed, but the scanner received HTTP 503 for page/header probes, so HTTP security headers were not assessed. It found no CAA record (low severity). Agent Ready's /docs scan failed with 0 pages scanned and a TLS handshake timeout; direct GETs later returned 404 for /robots.txt, /llms.txt, /sitemap.xml and /AGENTS.md, but 200 for /openapi.json and /health. Its crawler-block claim for robots.txt contradicted the direct 404 and is unconfirmed. These website-level llms/sitemap/AGENTS checks are not a valid readiness score for this API-only service; no agent-readiness pass is claimed and no robots policy was changed.
- No production SQL, database restore, snapshot extraction, branch creation, production secret access, OAuth refresh, Pinterest write, workflow pause/resume, PR, merge or deployment was performed by this continuation.
- Owner gates remain: decide whether the active main-branch hourly publisher and daily Learning Loop may continue before go-live; if the outcome of job 14 must be confirmed, authorize a narrowly scoped read-only production ledger/Pinterest verification. Separately authorize an owner-approved sanitized snapshot and isolated restore target. Keep Neon Free; do not touch the unsanitized local dump.


### Workflow observability patch — exact-head CI closure (2026-11-10)

- Commit 32485734d618706612013266bb3741fa899818cb adds the bounded workflow summary helper and behavioral tests. Commit 1a48d3cb15f1e817a9c5deff6f600f93854de1ea adds the new test module to the disposable PostgreSQL CI command and upgrades its checkout/setup-python actions to Node 24-compatible v7 releases; checkout credential persistence is disabled.
- The first run 42737465330 passed its selected 323 tests but did not include the new summary test module. The CI test list was corrected rather than treating that run as coverage.
- Final exact-head run 42737647489 at commit 1a48d3c: **328 passed, 0 failed, 1 non-blocking Starlette/httpx deprecation warning**. It included tests/test_workflow_summary.py, verified all 16 numbered migrations, confirmed synthetic fixtures were cleaned, and stopped the disposable PostgreSQL 16 service.
- The new summary helper exposes scheduler published/already_published booleans and Learning Loop aggregate failure counts/stages/statuses, without Pin IDs, affiliate URLs, per-Pin payloads or credentials. Missing pin_results remains unknown rather than fabricated zero. This is workflow observability only; it does not change scheduler cadence, job selection, Pinterest calls or production side effects.
- Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42737647489
- This patch is on the feature branch only. No PR, merge, deployment, production database action, workflow pause/resume, Pinterest write or real Pin/Board operation was performed.


### Python dependency vulnerability audit — PASS (2026-11-10)

- Added a blocking CI audit using pinned pip-audit 2.10.1 with strict dependency collection and a 15-second socket timeout against requirements.txt.
- Exact-head run 42738338668 at feature commit f2657d72ba9697cbc595f9ab2b15f7f94eb35abb completed successfully and reported: **No known vulnerabilities found**. The same run passed **328 tests, 0 failed, 1 non-blocking Starlette/httpx deprecation warning**, verified all 16 migrations, confirmed fixture cleanup and stopped disposable PostgreSQL 16.
- Scope: this audits the dependency set resolved from requirements.txt at run time. The repository does not provide a fully pinned lockfile/SBOM in this workflow, so the result is a point-in-time audit, not a guarantee about future unpinned resolutions or the live Render environment.
- Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42738338668
- The feature branch remains undeployed; no production deployment, database action, scheduler change or Pinterest write occurred.


### Runtime/development dependency boundary and Render deployment constraints (2026-11-10)

- Commit e1f1a6fee944bc2117b4483fbe9bcb6dee49b3ab separates runtime requirements from test-only tooling: requirements.txt now contains runtime libraries only; requirements-dev.txt contains pytest. A new behavioral test prevents pytest, bandit and pip-audit from entering the production runtime requirements. Local suite: **346 passed, 74 skipped, 1 existing Starlette/httpx warning**; the two PostgreSQL-admin integration modules are excluded locally and run in CI.
- Render service configuration was re-read: build command is `pip install -r requirements.txt`, so an approved future deploy of this branch will not install pytest in production. Current live main has not received this change.
- Exact-head CI run 42739207343 at e1f1a6f: **330 passed, 0 failed, 1 non-blocking Starlette/httpx deprecation warning**; pip-audit 2.10.1 audited both requirements.txt and requirements-dev.txt with strict collection and reported **No known vulnerabilities found**. All 16 migrations were recorded; synthetic fixtures were cleaned; disposable PostgreSQL 16 stopped.
- Render production service remains on the Free plan, one instance, auto-deploy from main, with healthCheckPath unset. The public /health and /openapi.json endpoints returned HTTP 200. The deployed service still runs Model 1; this feature branch is not deployed.
- Render's official documentation explicitly says Free web services are not intended for production applications; they spin down after 15 minutes idle, take about one minute to start, can restart at any time, and do not support shell/SSH access. This is a production availability/operations blocker, separate from the user's Neon Free constraint. No Render plan change was made.
- Render's default health check is a TCP probe; an HTTP health-check path is optional. The current /health route is liveness-only and does not prove database/provider readiness, so no healthCheckPath setting was changed. A production-grade readiness signal and the Render compute-plan decision remain owner gates.
- CI run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42739207343


### HTTP security-header remediation — feature-branch verification (2026-11-10)

- Direct HTTPS requests to the currently deployed Model 1 service showed no Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, Referrer-Policy or Permissions-Policy response headers on /health, /openapi.json or /docs. This was a measured gap, not merely a Sitelemetry scanner limitation.
- Added pure-ASGI SecurityHeadersMiddleware on the Model 2 feature branch. It applies nosniff, DENY framing, no-referrer and a restrictive camera/microphone/geolocation Permissions-Policy to API, docs, 404 and authentication-error responses. HSTS is added only when the ASGI scheme or trusted ingress X-Forwarded-Proto indicates HTTPS; plain HTTP does not receive HSTS. Existing response headers are preserved.
- Added tests for HTTPS API/docs/404/auth responses and for no HSTS over plain HTTP. The initial test-first run failed all five HTTPS cases, confirming the missing headers. After implementation, the focused header suite passed; the full local suite passed **353 tests, 74 skipped, 1 existing Starlette/httpx deprecation warning** (the two PostgreSQL-admin integration modules remain excluded locally). Bandit high/medium severity scan passed with exit code 0.
- The Model 2 disposable PostgreSQL CI workflow explicitly includes tests/test_security_headers.py. Exact-head CI run 42780473062 at commit 508c11f4420644f63610d837805ce9ac232bf7b7 passed: **337 passed, 0 failed, 1 non-blocking Starlette/httpx deprecation warning**. The run also audited both runtime and development requirements (pip-audit 2.10.1: no known vulnerabilities), verified all 16 migrations and fixture cleanup, and stopped disposable PostgreSQL 16. The CI test selection is narrower than the full local suite; it explicitly includes the security-header tests.
- This is feature-branch code only. The live Render service still runs Model 1 and has not received the headers. Post-deployment HTTPS header verification is therefore NOT TESTED; no production deployment or configuration change was made.
- Exact-head CI: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42780473062


### Latest exact-head continuation — 2026-11-10 (authoritative feature-branch status)

This section supersedes earlier references above to the latest feature-branch CI run or latest feature-branch commit. Historical run results remain valid for their respective checkpoints.

- Feature branch: `feat/model2-open-source-reuse`; exact HEAD: `56c7a0efcef6570a82730b5e0d8a433d934a64f7`. The worktree was clean and the branch synchronized with `origin/feat/model2-open-source-reuse` at verification. No PR exists; no merge or deployment was performed.
- Latest exact-head GitHub Actions run `42780726563` completed successfully on 2026-11-10. The explicit Model 2 PostgreSQL CI selection reported **337 passed, 0 failed, 1 non-blocking Starlette/httpx TestClient deprecation warning**. It audited runtime and development requirements with pip-audit 2.10.1 and reported **No known vulnerabilities found**; verified all 16 numbered migrations, synthetic Model 1/Model 2 fixture cleanup, and disposable PostgreSQL 16 teardown. This explicit CI selection is narrower than the local full suite; do not treat the counts as identical coverage.
- Local full suite excluding only `tests/test_model2_backup_restore.py` and `tests/test_model2_legacy_upgrade.py`: **353 passed, 74 skipped, 1 warning**. `compileall`, `git diff --check`, and Bandit high/medium severity scan passed. PostgreSQL-admin modules were not run locally; their disposable PostgreSQL coverage is in CI.
- Workflow outcome summaries now distinguish newly published from already-published scheduler jobs and aggregate Learning Loop failure stage/status counts without exposing Pin IDs, affiliate URLs, per-Pin payloads or credentials. Missing provider result data remains unknown, not zero.
- Runtime and development requirements are separated; Render's configured build command installs only `requirements.txt`. The dependency audit is a point-in-time resolved-dependency check, not a lockfile/SBOM or a guarantee about future resolution/live runtime packages.
- Pure-ASGI security response-header middleware and regression tests are present on this feature branch. It applies `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and HTTPS-only HSTS. These headers have **not** been deployed to Render; post-deployment verification remains NOT TESTED.
- Production remains Model 1 on Render Free. Render Free's sleep/cold-start/restart limitations remain an availability blocker. Neon remains Free with the previously verified 6-hour PITR window; no paid Neon plan or Cloudflare backup dependency is introduced.
- The successful encrypted backup restore rehearsal in backup-repository run `42731539863` remains limited to an isolated PostgreSQL 16 container. It does not replace a sanitized production-like Model 2 snapshot rehearsal or an owner-operated Neon restore/rollback rehearsal.
- **Owner decision still required:** whether the existing main-branch hourly Affiliate Scheduler Worker and daily Pinterest Learning Loop should remain active or be paused. Until explicitly decided, do not pause/resume either workflow, dispatch a worker, or inspect production publication state. Existing production side effects described above remain unchanged; the outcome of scheduler job 14's `published` versus `already_published` state remains UNKNOWN.
- Remaining release gates: sanitized production-like snapshot and isolated restore/rollback rehearsal; owner-approved Neon restore access, RPO/RTO and escalation path; production credential inventory and separately approved key rotation/re-encryption; production service/database access and log retention evidence; owner scheduler decision; repository merge-control decision; Render availability/readiness decision; and separate explicit approvals for migration, deployment and scheduler activation.

**Phase 10 remains PRE-RELEASE / BLOCKED.** Green feature-branch CI and successful encrypted backup recovery do not authorize production migration, deployment, credential rotation, scheduler changes or Pinterest publication.


### Owner decision — existing production schedules remain active (2026-11-10)

- Owner explicitly decided that the existing main-branch hourly Affiliate Scheduler Worker and daily Pinterest Learning Loop should **remain active**.
- This records the decision to preserve their current operating state. It is not an instruction to dispatch either workflow, change cron schedules, create/activate Model 2 schedules, or alter production configuration.
- No workflow was enabled, disabled, paused, resumed or dispatched for this decision. Existing production side effects continue under the already-configured `main` workflows.
- The existing uncertainty remains: scheduler job 14's wrapper output did not distinguish `published` from `already_published`; its publication outcome remains UNKNOWN. No production ledger or Pinterest verification was performed by recording this decision.
- The decision does not approve Model 2 merge/deployment, production migrations, credential rotation, database restore, or any new Pinterest publication.


### Synthetic pre-Model-2 rollback/recovery CI — PASS (2026-11-10)

- Added a separate test that captures a custom-format backup after synthetic legacy migrations 001–012, advances the source through Model 2 migrations 013–015, and restores the known-good pre-upgrade archive into a clean disposable PostgreSQL 16 database.
- Recovery checks verify the 13-file legacy migration ledger, absence of Model 2-only schema additions, and preservation of synthetic legacy schedule/job rows. The test restores a prior compatible schema rather than attempting unsafe down migrations.
- Exact-head CI run `42834166667` at commit `d57473554942972cdc45d52e987f8d7539cedae0`: **338 passed, 0 failed, 1 non-blocking warning**. All 16 current migration files were verified in the CI database; fixture cleanup and PostgreSQL service teardown passed.
- Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42834166667
- This closes the synthetic automated rollback/recovery test gap only. It does not establish a sanitized production-like restore, Neon PITR/restore capability, production RPO/RTO, or independent reviewer sign-off. The release scorecard remains partial for rollback and Phase 10 remains blocked.
- No production database, credentials, OAuth, scheduler, Pinterest API write, real Pin/Board, merge or deployment was used.

### PR #77 — Codex P2 timezone immutability remediation (2026-11-10)

- Codex completed review of exact PR head `3316814507155c83f885be8787799b442978e20a` and reported one new P2 in `app/model2_repository.py`: changing an account profile timezone while an immutable Model 2 schedule is active leaves the worker repeatedly rejecting due jobs because the schedule/profile timezones diverge.
- Remediation in progress: `save_account_profile` now reads the existing profile timezone under its existing `FOR UPDATE` lock. If a timezone change is requested, it checks for an active Model 2 schedule (`niche_id IS NOT NULL`) and raises `Model2ConflictError` before updating the profile. This shares the profile-row serialization lock used by schedule creation/activation, preventing a concurrent activation from racing the timezone change. Once the schedule is paused, the timezone may be changed and a replacement schedule created.
- Added a repository unit regression test and a disposable PostgreSQL integration test for rejection while active and successful change after pause. These tests are pending execution in CI; the current connected development device has no preinstalled pytest and local dependency installation is being prepared in an isolated virtual environment.
- The previous pre-publish-conflict P2 remains fixed and its review thread was resolved. The new timezone finding is not yet resolved; do not call the Codex review clean until a fresh review of the corrected commit is complete.
- No production DB, live schedule, credentials, OAuth, Pinterest API, Pin/Board, merge or deployment was touched. PR #77 remains review-only; Phase 10 remains PRE-RELEASE / BLOCKED.

### Timezone immutability fix — exact-head CI closure (2026-11-10)

- Final code/test head before this evidence update: `51d853f2dba9878a97dd5a12e85e5369c2b56a8d`.
- First CI attempt on `2680d35` exposed only two regression-test message-regex mismatches; application behavior reached the intended conflict path. Updated the error wording to be stable and explicit in `51d853f`.
- Exact-head CI on `51d853f`: Python CI run `42867379931` PASS (**438 passed, 1 skipped, 1 warning**); Python tests run `42867379978` PASS (**438 passed, 1 skipped, 1 warning**); Model 2 PostgreSQL integration run `42867379850` PASS (**347 passed, 1 warning**). The PostgreSQL workflow reported **No known vulnerabilities found**, verified all 16 numbered migrations, confirmed Model 2 and synthetic Model 1 fixture cleanup, and stopped disposable PostgreSQL 16.
- All three required PR checks are green for exact head `51d853f`. The timezone regression tests now prove active Model 2 schedule blocks profile timezone change and a paused schedule permits it.
- A fresh Codex review was requested after the code fix. Its final result is not yet available; do not call the independent review clean until the review receipt/comments are checked.
- No production database, credentials, OAuth, scheduler dispatch/change, Pinterest API write, Pin/Board, merge or deployment occurred. PR #77 remains open and review-only. Phase 10 remains PRE-RELEASE / BLOCKED.

### Independent Codex review closure — timezone finding (2026-11-10)

- Codex completed a fresh review of `18aa83a325e2c5597dc6c832160de2d467adbcfd`: `has_any_findings=false`, `has_unresolved_findings=false`; receipt states “Didn't find any major issues. Nice work!”.
- The timezone P2 review thread was explicitly resolved after the guarded timezone change and exact-head CI passed. All four Codex review threads on PR #77 are now resolved.
- PR #77 remains open for owner review; this is not merge or production-release approval. Phase 10 remains PRE-RELEASE / BLOCKED by the independent production readiness gates documented above.


### Latest production-readiness continuation — exact-head verification (2026-11-10)

**Authoritative feature-branch head:** `7bbcd1332623d0abf169fc06ff1c94f3402a6ac6`  
**PR:** [#77](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/77) — OPEN, NOT MERGED, NOT DEPLOYED.

#### Additional side-effect and quota hardening

- **Pinterest Board creation:** migration 016 adds an account-scoped durable idempotency ledger. `create_board` requires `Idempotency-Key`, replays stored success, rejects payload mismatch, and blocks in-progress/uncertain outcomes. Timeouts, unreadable success responses and 5xx responses are treated as uncertain; no automatic retry can issue a second provider POST for the same key.
- **Pinterest OAuth refresh:** official Pinterest authentication documentation describes successful continuous refresh as returning a new access token and continuous refresh token. Both the Hub-facing refresh endpoint and internal auto-refresh path previously lacked durable uncertainty state. Migration 017 now records a SHA-256 fingerprint of the current access/refresh token generation (never raw tokens), and both paths share the ledger; the internal path also retains its per-account advisory lock. Both paths block duplicate/in-progress/uncertain attempts and mark timeouts/5xx/incomplete responses uncertain. Success is finalized only after encrypted token persistence. A fresh access token is not refreshed again unnecessarily. Refresh requests now send only documented refresh-grant parameters (grant_type and refresh_token), not the unsupported continuous_refresh parameter. Ambiguous token generations require operator-controlled recovery/reconnect.
- **Legacy Model 1 scheduler quota:** both legacy daily-quota SQL predicates now count `uncertain` jobs alongside `processing` and `succeeded`. This closes a gap where an ambiguous Pin outcome could have failed to consume quota and allowed an extra same-day job. A synthetic regression test covers the last available daily slot.
- Restore rehearsal documentation and disposable CI cleanup checks now include migrations 016 and 017 and the Pinterest refresh-operation ledger.


- **Disconnect semantics:** local disconnect only changes the stored credential status to revoked; it does not call Pinterest's token-revocation endpoint. Pinterest's official Postman collection documents that endpoint as currently supporting system-user tokens only; this integration uses user Authorization Code tokens. The API response now explicitly returns \`local_access_disabled: true\` and \`provider_token_revoked: false\` so the UI cannot imply remote revocation.

#### Exact-head CI evidence

- Python tests run [42909034642](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42909034642): **445 passed, 1 skipped, 1 non-blocking warning**.
- Python CI run [42909034636](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42909034636): Bandit passed; pip-audit reported **No known vulnerabilities found**; **445 passed, 1 skipped**.
- Model 2 PostgreSQL integration run [42909034522](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42909034522): **351 passed**; all **18 numbered migrations** recorded; Model 2, Model 1 and OAuth refresh fixtures cleaned; disposable PostgreSQL container stopped.
- The Python test run includes synthetic timeout/replay tests for OAuth refresh and Board creation, plus the legacy uncertain-quota regression. The PostgreSQL run exercises the real encrypted OAuth credential persistence and operation ledger against disposable PostgreSQL; Pinterest remains mocked.

#### Remaining release gates — unchanged

- No sanitized production-like snapshot restore/rehearsal or owner-verified Neon PITR/restore access, RPO/RTO and escalation evidence.
- No production credential inventory, approved key rotation/re-encryption, rollback evidence, or complete service-key/log-retention operational review.
- Existing hourly Affiliate Scheduler Worker and daily Pinterest Learning Loop remain active on main by owner decision. They were not dispatched, paused, resumed or changed in this continuation.
- Render Free cold-start/restart limitations and readiness/health-check design remain unresolved availability concerns.
- No production database migration, production credential read/rotation, OAuth refresh, Pinterest API write, real Pin/Board creation, scheduler dispatch/change, PR merge or deployment was performed.

**Phase 10 remains PRE-RELEASE / BLOCKED.** Green disposable CI verifies feature-branch code only; it does not satisfy production restore rehearsal, availability, security-operations, owner-approval or deployment gates.
