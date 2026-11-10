# Model 2 — Sanitized Snapshot Restore and Migration Rehearsal

**Status:** Operator runbook prepared; rehearsal NOT EXECUTED.  
**Applies to:** PR #77, branch `feat/model2-open-source-reuse`.  
**Purpose:** Prove that a sanitized, production-like PostgreSQL snapshot can be restored into an isolated environment, upgraded through the repository migrations, validated, and recovered to its pre-upgrade state without touching production.

This document is a procedure, not authorization. It does not authorize reading production data, creating/downloading a production backup, changing Neon settings, restoring any shared database, changing credentials, running scheduler workflows, or publishing to Pinterest.

## 1. Non-negotiable safety boundary

- Use a separately approved, isolated rehearsal environment. It must not be the production Neon project, production branch, Render database, or any database reachable by the deployed service.
- Never put a production connection string in a developer shell, CI variable, issue, chat, log, or this document.
- Never restore a production backup directly over production or a shared/staging database.
- Do not copy live OAuth access/refresh tokens, API keys, session cookies, encryption keys, webhook secrets, or service credentials into the rehearsal dataset. Prefer omitting credential rows entirely. If schema coverage requires rows, replace values with unmistakable nonfunctional synthetic placeholders before the archive leaves the controlled source environment.
- Remove or irreversibly replace direct identifiers and sensitive payloads in products, publication metadata, analytics, logs, and audit evidence. Review free-text fields and URLs; they can contain identifiers or secrets.
- Do not run application startup hooks, scheduled workers, GitHub workflow dispatches, background tasks, or any code path that can call Pinterest, affiliate providers, Cloudflare, DeepSeek, or other external services. The rehearsal must use SQL/migration tooling only.
- Block outbound network access from the rehearsal runner where practical. At minimum, ensure no production secrets or provider credentials are present.
- No real Pin, Board, OAuth refresh, scheduler claim, or publish operation is part of this rehearsal.
- Stop immediately if the target identity, database isolation, sanitization, or restore point cannot be proven.

## 2. Roles and evidence

The owner/operator must identify and record:
- rehearsal operator and independent reviewer;
- approval/ticket reference and approved time window;
- source snapshot identifier and source timestamp (record metadata only, never credentials);
- target project/branch/database identity proving isolation;
- PostgreSQL server version and migration tool/version;
- archive encryption and checksum verification result;
- start/end timestamps and measured restore/migration/recovery durations;
- test results, exceptions, cleanup and artifact-destruction evidence.

The operator and reviewer must be different people for the final sign-off. The current shared service API key is not a human identity mechanism; do not use it as proof of individual approval.

## 3. Pre-flight — do not proceed until every item passes

- [ ] Written owner approval for a one-time sanitized snapshot export and isolated rehearsal.
- [ ] Confirmed source snapshot mechanism, retention and access permissions with the database owner.
- [ ] Confirmed target is a disposable isolated PostgreSQL environment with a unique name and no production service connection.
- [ ] Target has no production secrets, provider credentials, OAuth tokens, or application service key.
- [ ] Outbound network egress is blocked or constrained to the approved database/artifact endpoints.
- [ ] Backup archive is encrypted at rest and in transit; decryption material is handled out-of-band by the approved secret manager.
- [ ] Sanitization procedure is reviewed before export; post-sanitization inspection is mandatory.
- [ ] A clean target can be destroyed and recreated without affecting any shared resource.
- [ ] Exact PR head and migration file set are recorded. For the current branch, migrations 014 and 015 are the Model 2 additions; the repository currently contains 16 numbered migration files because the legacy sequence has two distinct 009-prefixed files. Do not infer ordering from filename sorting alone; use the repository's migration ledger/runner ordering.

**Abort conditions:** production endpoint/hostname appears in target configuration; any live secret is found; source/target identity is ambiguous; snapshot checksum fails; sanitization is incomplete; unexpected network egress occurs; or a migration attempts destructive/backfill behavior not covered by the approved plan.

## 4. Create and sanitize the rehearsal snapshot

1. Owner/operator uses the approved database backup process to capture a consistent snapshot. Record the snapshot ID and timestamp, not its connection string or secret material.
2. Restore the snapshot into a quarantine database that is isolated from application services and outbound network access.
3. Apply the approved sanitization transformation in quarantine:
   - remove credential/token/session tables or replace all sensitive values with nonfunctional synthetic values;
   - replace account identifiers with stable synthetic IDs and update every referencing row consistently;
   - replace personal names, emails, phone numbers, addresses and free-text identifiers;
   - replace product/affiliate URLs and any embedded tracking or private query parameters;
   - remove raw provider responses, request/response headers, cookies and diagnostic payloads that may contain secrets;
   - retain only the minimum structural and representative relational data needed to test migrations and legacy compatibility;
   - preserve representative legacy schedule/job states only as synthetic fixtures, including queued, processing, succeeded, failed and uncertain states where valid.
4. Run automated secret/PII scans over the sanitized export and a manual review of high-risk text/URL fields. A scan alone is not sufficient.
5. Generate a cryptographic checksum of the sanitized archive. Encrypt it, restrict access, and transfer it only through the approved artifact channel.
6. Independent reviewer verifies the sanitization report and a sample of the restored sanitized records before migration testing.
7. If any secret or direct identifier is discovered, quarantine and destroy the artifact, document the incident, and restart from a fresh sanitized snapshot. Do not patch the leaked artifact in place and continue.

## 5. Restore baseline into disposable PostgreSQL

1. Provision a fresh disposable PostgreSQL instance with a supported version matching the intended production compatibility target. Record the exact server version and extensions.
2. Confirm the database is empty and the target identity is the approved disposable target.
3. Verify archive checksum before decryption/restore. Decrypt only into a protected temporary location with restrictive filesystem permissions.
4. Restore using the approved PostgreSQL restore utility and options compatible with the archive format. Do not use a production connection string or a shared database URL.
5. Verify baseline integrity before applying migrations:
   - expected schemas, tables, indexes, constraints and extensions exist;
   - expected legacy migration ledger entries are present;
   - row counts are within the approved sanitized fixture ranges;
   - no Model 2-only schema objects from migrations 014/015 are present in a true pre-Model-2 baseline;
   - legacy schedule/job and publication relationships are internally consistent;
   - no secrets, live tokens or direct identifiers remain.
6. Capture baseline schema-only and data-integrity reports. Do not export raw row data into CI logs.

## 6. Apply migrations and test compatibility

1. Check out the exact reviewed PR head recorded in the release ticket. Record the full commit SHA.
2. Use the repository's established migration runner and its declared ordering. Do not hand-edit migration SQL or skip migration ledger checks.
3. Apply pending migrations through the full current branch migration set, including:
   - migration 014: account-aware Model 2 scheduling additions;
   - migration 015: scheduler reconciliation audit additions.
4. Capture each migration's start/end, exit status and ledger result. Stop on the first error; do not manually mark a failed migration as applied.
5. Validate legacy compatibility:
   - pre-existing Model 1 schedules remain legacy rows with `niche_id IS NULL`;
   - existing legacy schedule/job/publication records remain present and linked;
   - legacy schedule reads and permitted updates still behave as before;
   - no legacy business rows were silently backfilled, deleted, or rewritten.
6. Validate Model 2 schema:
   - account/niche foreign-key and composite ownership constraints;
   - schedule indexes and active-schedule uniqueness;
   - Model 2-only trigger behavior and legacy-row exemption;
   - reconciliation audit table constraints and append-only protections;
   - uncertain-job/account/idempotency lineage constraints expected by the application.
7. Run the repository's PostgreSQL integration test selection against this disposable target. Do not invoke production endpoints or external provider integrations.
8. Compare post-migration schema, ledger, and approved row-count/integrity summaries with the baseline. Investigate every unexpected difference.

## 7. Recovery / rollback rehearsal

The supported recovery exercise is restoration of the known-good pre-upgrade snapshot into a fresh disposable database, not destructive down-migrations against the upgraded database.

1. Preserve the upgraded rehearsal database and its logs as evidence until the reviewer accepts the result.
2. Provision a second clean disposable PostgreSQL target.
3. Restore the same verified, sanitized pre-upgrade archive into that second target.
4. Verify the restored migration ledger is the expected pre-upgrade ledger and that Model 2-only objects from migrations 014/015 are absent.
5. Verify representative synthetic legacy rows and relationships match the baseline integrity report.
6. Record measured recovery time. Repeat once if required by the approved RTO target.
7. Demonstrate that the upgraded rehearsal database and the recovered baseline database are separate targets; no in-place destructive rollback is permitted.
8. If the application rollback scenario is tested, use the prior application artifact only against a disposable database with additive schema retained. Confirm legacy explicit-column queries still work. Do not drop migration 014/015 objects or audit data as a rollback shortcut.

**Important:** A successful disposable restore does not prove Neon PITR, Neon backup retention, owner restore permissions, production RPO/RTO, or production recovery readiness. Those require separate owner-operated evidence from the actual Neon project and approved plan.

## 8. Acceptance criteria

The rehearsal passes only if all are true:

- [ ] Snapshot origin, timestamp and target isolation are documented.
- [ ] Sanitization is independently reviewed; no production secrets or direct identifiers remain.
- [ ] Archive checksum and encryption checks pass.
- [ ] Baseline restore completes without errors.
- [ ] All pending migrations apply in repository order; migration ledger is complete and consistent.
- [ ] Legacy Model 1 rows and behavior remain intact; no unexpected backfill or data mutation occurs.
- [ ] Model 2 constraints, indexes, triggers and reconciliation audit protections validate.
- [ ] PostgreSQL integration tests pass against the isolated target.
- [ ] Fresh-target recovery from the pre-upgrade archive passes and restores the expected legacy schema/data state.
- [ ] Measured restore and recovery times meet owner-approved targets, or the gap is explicitly accepted as a blocker.
- [ ] Independent reviewer signs the evidence package.
- [ ] Temporary databases, decrypted archives and working copies are destroyed; encrypted evidence retention follows the approved policy.

A failure or missing evidence means **NOT PASSED**. Do not convert a partial pass into release approval.

## 9. Evidence package template

Store only in the approved private release-evidence location:

| Field | Value |
|---|---|
| Approval/ticket | |
| Operator / independent reviewer | |
| PR head SHA | |
| Snapshot ID and timestamp | |
| Sanitization report reference | |
| Archive checksum / encryption verification | |
| Source and target isolation evidence | |
| PostgreSQL version / extensions | |
| Migration ledger result | |
| Legacy compatibility result | |
| Model 2 schema validation result | |
| Integration test run URL / summary | |
| Baseline restore duration | |
| Recovery restore duration | |
| RPO/RTO target and measured result | |
| Cleanup/destruction evidence | |
| Exceptions / unresolved findings | |
| Reviewer decision and timestamp | |

Never place connection strings, API keys, OAuth tokens, encryption keys, raw sanitized data, or sensitive query output in this evidence package.

## 10. Separate release approvals still required

Passing this rehearsal does not authorize:
- Neon production migration or restore;
- production credential inventory disclosure or key rotation;
- Render deployment or application promotion;
- merge of PR #77;
- scheduler activation, dispatch, pause/resume, or schedule creation;
- Pinterest OAuth refresh/reconnect or Pinterest API writes;
- real Pin or Board creation.

Each requires its own explicit owner approval and change window. Phase 10 remains **PRE-RELEASE / BLOCKED** until all release gates are independently evidenced and approved.
