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
| Quota concurrency | Pass in CI | Same-account serialization; different-account parallel claims; uncertain quota hardening awaits CI |
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
- [ ] Record Neon project's backup/PITR availability, retention and recovery-point capabilities from owner-authorized evidence.
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
- [ ] Complete static review of authentication, authorization boundaries, account scoping, secret redaction and error handling.
- [ ] Obtain owner-authorized evidence for production service access, database roles, log access, retention and deletion policy.
- [ ] Record findings and remediate code-owned issues on this feature branch; production configuration changes require separate approval.

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
- This is a feature-branch code change after the previously recorded exact-head CI run. **Exact-head CI has not yet been run for this new change.** Do not call the branch release-verified until CI is rerun.
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
