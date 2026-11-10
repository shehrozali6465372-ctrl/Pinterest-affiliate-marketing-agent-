# Phase 10 — Sanitized PostgreSQL Restore and Rollback Rehearsal

## Purpose and safety boundary

This runbook defines the evidence required for the Phase 10 migration/restore/rollback gate. It is a procedure specification only. Writing it does not authorize access to production rows, creation of a Neon branch, a production dump, a restore, a migration, a deployment, or scheduler changes.

**Never use the known local `pinterest_affiliate_20261103.dump` for this rehearsal.** It is an older Model 1 dump that contains credential-table data entries and encrypted-token columns, and it does not establish the current Model 2 migration state. Do not extract its table data, restore it, or copy it into a staging environment.

The preferred rehearsal input is a purpose-built synthetic fixture set generated from the current migration schema. If an owner later requires a production-derived snapshot, that is a separate workflow requiring explicit source approval, a documented sanitization method, an isolated target, and independent review before any data is exported or imported.

## Non-negotiable controls

- Keep Neon on Free. Do not create a paid-plan dependency or use Cloudflare/R2 in the backup or restore path.
- Use a disposable PostgreSQL 16 instance or another explicitly approved isolated target. Do not point restore tooling at the production Neon URL.
- Do not use production credentials, access tokens, refresh tokens, encryption keys, Pinterest account identifiers, real Pin IDs, affiliate URLs, personal data, or production content in fixtures.
- Generate synthetic account identifiers that satisfy the schema (for example, `pinterest:test-account-0001`) and synthetic foreign-key relationships. Never substitute a real account ID.
- Credential fixture rows, if required by FK constraints, must use test-only encryption material and synthetic token plaintext created solely for the test. They must never be accepted by production services. Do not copy ciphertext from production.
- Keep test secrets in ephemeral CI/runtime secret storage. Never print them, commit them, include them in logs, or place them in the backup artifact.
- No real Pinterest API calls, Pin creation, Board creation, scheduler execution, OAuth refresh, or external side effects. Network egress should be disabled unless a separately approved test explicitly needs it; this rehearsal does not.
- Preserve the source backup and its checksum as immutable evidence. Do not overwrite or delete existing backup releases.
- Destroy the disposable target and temporary plaintext/decrypted files after evidence capture. Retain only sanitized logs, checksums, migration/test reports, and the approved run record.

## Data minimization and sanitization contract

For the baseline rehearsal, create synthetic data from schema definitions rather than copying production rows. The fixture generator must use deterministic synthetic values and document its seed/version.

If a production-derived sanitized export is separately approved, apply a strict allowlist and review every table/column against the live migration schema before export:

1. **Exclude `pinterest_credentials` production rows entirely.** The schema contains `access_token_ciphertext` and `refresh_token_ciphertext`; encrypted does not mean safe to copy. If FK coverage is needed, insert synthetic test-only credential rows after restore using test-only keys.
2. Replace every account identifier, Pinterest user ID, username, Pin ID, product identifier, schedule/job identifier, and other externally correlatable identifier with a deterministic synthetic value. Remap all foreign keys consistently; do not retain a reversible mapping in the artifact.
3. Remove affiliate URLs, tracking parameters, product source URLs, image URLs, external URLs, raw provider payloads, cookies, authorization headers, OAuth material, API keys, and any free-form field that may contain a secret or personal data.
4. Replace product titles, descriptions, generated content, board names, operator notes, reconciliation evidence, and other free text with synthetic values. Do not rely on regex-only redaction for arbitrary text.
5. Keep analytics only when the owner approves the purpose and the values are either generated synthetically or aggregated/de-identified with a documented method. Preserve unknown values as `NULL`; never manufacture zeroes for missing metrics.
6. Preserve referential integrity and the minimum state combinations needed to exercise the target migrations (e.g. account/niche mappings, schedules, queued/processing/succeeded/failed jobs, publication and analytics lineage). All records must be synthetic and clearly marked as test fixtures.
7. Produce a sanitization manifest containing source identity/version (not credentials), export timestamp, table/column allowlist, transformations, row counts, foreign-key checks, reviewer approval, and artifact SHA-256. Do not include raw values or reversible identity maps.
8. A reviewer independent of the export operator must verify the manifest and inspect the resulting schema/data classifications before the artifact is accepted. If any field's sensitivity is uncertain, exclude it.

A sanitized production-derived snapshot is **not approved by this document**. It requires separate explicit owner approval before source access/export.

## Rehearsal procedure

### A. Preflight and artifact validation

- Record the approved source artifact identifier, SHA-256, creation time, PostgreSQL major version, and sanitization-manifest approval. For synthetic fixtures, record generator commit/version and seed instead.
- Verify the artifact is from the designated private GitHub backup repository and is encrypted at rest when stored as a backup release. Verify checksum before decryption.
- Decrypt only into a permission-restricted ephemeral workspace. Never place plaintext dumps in the repository, persistent shared storage, or logs.
- Confirm target connection identity before any restore: disposable PostgreSQL 16 only; fail closed if host/database identity is not the approved isolated target. Do not use `DATABASE_URL` inherited from production.
- Capture target's initial empty state and PostgreSQL version. No Neon production connection is permitted.

### B. Restore and migration verification

- Restore the approved sanitized artifact into the empty disposable target, or construct the synthetic baseline there. Record the exact command/tool version and exit status.
- Apply all 16 registered SQL migration files in the exact order used by `app/database.py` (`sorted(migrations/[0-9]*.sql)`), including both distinct `009` files. Do not hand-edit migration files or skip/reorder entries.
- Verify the migration ledger contains every expected migration filename exactly once, including both `009` files, with no missing entries or failed/in-progress entries.
- Verify required tables, indexes, constraints, triggers, and functions exist. Include Model 2 account/niche registry, publication attribution, learning lineage, account-aware scheduling, and reconciliation audit objects.
- Verify FK integrity, unique constraints, immutable attribution/audit behavior, and account/niche isolation using synthetic accounts.
- Run the PostgreSQL integration tests and record exact test counts, failures, warnings, and fixture cleanup. Test failures are blockers; do not waive them by editing the evidence.

### C. Application compatibility and rollback rehearsal

- Use a build from the exact candidate commit and a non-production configuration containing only test credentials and the isolated database URL.
- Verify read-only health/readiness and representative authenticated read paths. Verify account isolation and that no production endpoints, provider calls, or scheduled workers are reachable from the test environment.
- Exercise the documented rollback plan against the disposable target only. Record the pre/post schema version, data-integrity checks, application version, commands, timings, and outcome.
- Do not assume a down migration is safe. For destructive or non-reversible schema changes, rollback means restoring the pre-change isolated backup and deploying the compatible prior application build. Document any data loss explicitly.
- Re-run integrity checks and the relevant tests after rollback. A successful forward migration without a successful rollback/recovery rehearsal does not close this gate.

### D. Cleanup and evidence

- Stop the disposable PostgreSQL service and remove temporary containers, volumes, decrypted dumps, and workspace files according to the approved retention policy.
- Verify cleanup; record only non-sensitive evidence (artifact digest, commit, migration ledger summary, test summary, restore/rollback exit status, cleanup confirmation, operator/reviewer, timestamps).
- Do not retain tokens, ciphertext, raw dumps, provider payloads, personal data, or reversible pseudonymization maps in the evidence bundle.

## Required pass criteria

The gate is PASS only when all are true:

- Owner-approved sanitized/synthetic input and independent sanitization review are recorded.
- Artifact checksum and decryption verification pass where applicable.
- Restore completes on the isolated PostgreSQL 16 target, with production Neon untouched.
- All 16 registered migration files are applied and the ledger/schema/constraints/triggers are verified.
- PostgreSQL integration tests pass, account-isolation checks pass, and no external side effects occur.
- Rollback/recovery to the prior compatible state succeeds and post-rollback integrity checks pass.
- Ephemeral resources and plaintext artifacts are confirmed cleaned up.

Any missing approval, unknown data classification, production connection, checksum mismatch, migration failure, test failure, rollback failure, or incomplete cleanup is **BLOCKED/FAIL**, not a conditional pass.

## Current status (2026-11-10)

- Runbook specification: documented; not executed.
- Approved sanitized production-derived snapshot: NOT PROVIDED / NOT APPROVED.
- Synthetic fixture restore/rollback rehearsal under this runbook: NOT RUN.
- Known local 2026-11-03 dump: EXCLUDED; do not use.
- Production Neon restore/migration: NOT AUTHORIZED and NOT PERFORMED.
- Phase 10 restore/rollback gate: **BLOCKED** pending owner-approved input and isolated rehearsal evidence.
