# Model 2 — Frozen Architecture Baseline

**Status:** FROZEN — owner directed that the architecture be locked before implementation (2026-11-08). Changes require an explicit owner-approved architecture revision.
**Date:** 2026-11-08
**Repository baseline:** isolated worktree `/root/restore-staging/Pinterest-Agent-model2-worktree`, branch `feat/model2-open-source-reuse`, based on Agent `origin/main` commit `785efd99849627062c1fff8504d21ca91abfee8e`.
**Change policy:** additive, reuse-first, account-isolated. Verified suitable open-source solutions must be reused; custom implementation is allowed only for documented residual gaps. Owner-approved clarification/addendum dated 2026-11-08. No production operation is authorized by this document.

## 1. Architecture objective

Extend the existing Pinterest Affiliate Marketing Agent from its current Model 1 single-account-oriented capabilities toward Model 2 multi-account and multi-niche operation, with account-owned configuration and niche-scoped descriptive learning.

Model 2 is an extension around Model 1, not a replacement. The existing production publishing and analytics foundations remain the system of record. New capabilities must call existing domain services and repositories rather than duplicate them.

## 2. Non-negotiable engineering rules

1. **Inspect before implementing.** Search the current mainline code, migrations, tests and deployed contracts before adding any component.
2. **Never rebuild completed functionality.** If a required capability already exists and is verified, reuse it. If partially implemented, add only the missing behavior. Record the exact existing module/API/test as evidence.
3. **No parallel core systems.** Do not create a second Pinterest publisher, scheduler, OAuth credential vault, publication ledger, raw Pin analytics store, image pipeline, or generic workflow engine.
4. **Single write boundary.** All Pinterest Pin creation must continue through `app/publishing_gateway.py`; no Model 2 route or worker may call Pinterest `POST /pins` directly.
5. **Account isolation is mandatory.** Every account-owned read/write must be authorized against the authenticated caller and canonical `account_id`. A caller-supplied account ID is not proof of ownership.
6. **Evidence-based learning.** Learning data must be derived from real persisted analytics and publications. Unknown metrics remain NULL/unknown; never manufacture zeroes or synthetic observations.
7. **Preserve current safeguards.** Keep draft-first behavior, idempotency, publication ledger checks, uncertain-outcome blocking, API-key fail-closed behavior, existing rate/size limits and read-only Pinterest verification.
8. **No secrets in Model 2 domain data.** OAuth tokens/ciphertext, API keys, cookies, browser sessions and affiliate secrets must not be copied into profile/niche tables, logs, docs or test fixtures.
9. **No external image hosting.** Preserve direct Base64 image submission to Pinterest; do not introduce Cloudflare Images or another host as a Model 2 dependency.
10. **Open-source-first implementation.** For every genuine gap, evaluate existing project code and suitable open-source solutions before writing custom code. Verify repository identity, maintenance/release state, API compatibility, security evidence, dependency impact and exact license obligations. Reuse a suitable verified solution; custom-build only the smallest residual gap when no suitable verified option exists. Never assume a project's maintenance, security, compatibility or license without evidence.
11. **No unapproved license imports.** AGPL-3.0 code (including previously inspected Postiz/Postmill references) is not approved for import without separate owner authorization after license review. Architecture references do not authorize code copying.
12. **No scope creep.** No ads:read/audience-insights consent, predictive ML, autonomous cross-account publishing, auto-board creation, browser coupling or production migrations are included in this baseline.
13. **Verify before advancing.** Each phase requires focused tests, regression tests, security review and documented evidence. A test that was not run must be reported as not run.

## 3. Existing Model 1 capabilities — reuse, do not recreate

The following existing components were inspected in this worktree. Their existence is verified by source inspection; production behavior must still be distinguished from local source presence.

| Capability | Existing implementation | Model 2 rule |
|---|---|---|
| Encrypted Pinterest OAuth credential storage and account lookup | `app/credential_vault.py`; `pinterest_credentials` | Reuse. No second vault or token table. |
| Canonical account identity | Existing `account_id` values in credential/publication records, format `pinterest:<user_id>` | Reuse exact canonical ID. Never mint a parallel account identity. |
| Single controlled Pin publisher | `app/publishing_gateway.py` | Reuse exclusively for every Pin write. |
| Publication reservation, idempotency and outcome ledger | `app/database.py`; `pin_publications` | Reuse. No duplicate ledger. |
| Workflow/content generation | `app/workflow.py`, `app/content_generation.py` and related modules | Extend only through existing workflow boundaries; no second workflow engine. |
| Product records and content versions | Existing product/content persistence in `app/database.py` and migrations | Reuse existing entities and lifecycle. |
| Draft-first affiliate scheduler / job queue | `app/affiliate_scheduler.py` and existing DB functions | Reuse. Multi-account fan-out is a later integration, not a new scheduler. |
| Direct image bytes to Pinterest | Existing workflow media path and `image_base64` submission | Reuse. No image-hosting subsystem. |
| Pin-level organic analytics ingestion | `app/learning.py`; `pin_analytics_snapshots` | Reuse as raw source of truth. Do not create another raw analytics table. |
| Descriptive Learning Loop | `app/learning.py` | Reuse ingestion and calculations; add only account+niche grouping/aggregation. |
| API-key authorization and protected routes | `app/main.py` (`require_api_key` / configured-key guards) | Reuse and apply consistently to new routes. Do not create a weaker auth path. |
| Read-only Pinterest account/board/Pin operations | Existing Pinterest client and verification routes | Reuse. No test may create a real Pin or Board. |

**Important distinction:** source inspection confirms these modules and contracts exist. It does not, by itself, prove every provider interaction or production deployment is currently healthy. Preserve the existing project CONTEXT checkpoints for their separately evidenced production status.

## 4. Model 2 target architecture

### 4.1 Logical components

A. **Account Registry (new, non-secret metadata only)**
- One profile per canonical connected Pinterest `account_id`.
- Stores display/operational metadata only; never credentials.
- An account profile is created only through an explicit authenticated onboarding action after checking that the same account exists as connected in the existing credential vault.
- Owner decision (2026-11-08): one owner/operator manages multiple Pinterest accounts. Model 2 is deployment-scoped to this operator; do not introduce a multi-tenant user table or synthetic owner identity. Existing shared API key is service authentication only, not proof of a distinct human identity. Registry writes remain behind the existing protected operator/service boundary; do not claim multi-user isolation.

B. **Niche Registry (new taxonomy)**
- Canonical niche identifier/slug, human-readable name, optional target market/region and active state.
- Niche records are reusable taxonomy entries; account-specific settings belong to the mapping, not the global niche row.
- Slug normalization and uniqueness must be deterministic.

C. **Account–Niche Assignment (new explicit mapping)**
- Connects an account profile to one or more niches.
- Stores account-specific targeting/configuration and active/paused state.
- At most one active primary niche per account.
- Every mapping must be constrained to an existing account profile and niche.
- No implicit default assignment or silent backfill of existing production accounts.

D. **Existing Content / Product / Workflow services (reuse)**
- Existing products, affiliate destination handling, content versions, prompt/generation services and workflow remain authoritative.
- Model 2 may select a niche assignment as validated input/context, but it must not create parallel product/content/workflow tables without a separately approved need.
- Affiliate destination URLs remain supplied/validated through existing mechanisms; do not invent Amazon affiliate URLs or tracking IDs.

E. **Existing Publishing and Scheduler services (reuse)**
- Every Pin creation goes through the one publishing gateway and its existing ledger.
- Scheduler stays draft-first and existing idempotency/uncertain-outcome controls remain authoritative.
- Account-aware routing is not enabled until account ownership, board association, daily limits, uniqueness keys and recovery behavior are fully specified and tested.
- No automatic board creation.

F. **Existing Raw Analytics + new Niche Learning Projection**
- Raw Pin-level analytics remain in `pin_analytics_snapshots`, joined to actual publication records.
- Niche attribution is explicit and publication-scoped through model2_publication_niche_attributions, tied by composite foreign keys to the exact publication account and account–niche assignment. Attribution is immutable and must be written in the existing gateway reservation transaction before provider network I/O. Learning aggregates must additionally enumerate their exact raw pin_analytics_snapshots rows through model2_learning_snapshot_sources; deferred constraints verify source counts. Each source row copies the exact JSONB metrics from the referenced raw analytics row at insert time, preserving historical evidence when Model 1 later refreshes its raw row in place. Never infer niche from a user-supplied query at aggregation time.
- New niche learning snapshots are derived aggregates with period bounds, sample counts, source counts and metric completeness.
- Account+niche aggregation is isolated; cross-account/global aggregation is excluded unless separately approved.
- No predictive model training until adequate longitudinal observations, leakage-safe time splits, baseline comparisons and evaluation gates are approved.

G. **Existing Operations Dashboard (reuse, then extend read-only)**
- Add account/niche visibility only after repository contracts and authorization tests are complete.
- Dashboard reads must not trigger Pinterest writes, token refresh, scheduling, generation or mutation.

### 4.2 Data flow

1. Authenticated operator selects an already connected Pinterest account.
2. Server validates canonical account ID and performs a read-only connected-credential existence check through the existing vault/repository boundary; token material is never returned to the route.
3. Operator explicitly creates/updates the non-secret account profile and selects/creates niche taxonomy entries.
4. Server creates an explicit account–niche mapping after validating account access, niche state and primary-niche uniqueness.
5. Existing product/content workflow receives a validated account+niche context; existing generation and draft persistence are reused.
6. Any later publication request goes only through the existing publishing gateway, which retains idempotency and ledger protections.
7. Existing analytics ingestion stores raw provider metrics against real Pins.
8. A separate projection process/repository derives niche-scoped descriptive snapshots only from correctly attributed source rows; no fabricated metrics.
9. Read-only dashboard/API surfaces account and niche configuration plus aggregate evidence.

## 5. Data ownership and proposed schema boundary

The revised schema proposal is additive and isolated to these six new tables:

- `model2_niches`: canonical niche taxonomy.
- `model2_account_profiles`: non-secret metadata keyed to canonical `account_id`.
- `model2_account_niches`: explicit account-to-niche assignment and account-specific settings.
- `model2_learning_snapshots`: derived account+niche descriptive aggregates.

The draft migration currently present is `migrations/013_model2_account_niche_registry.sql`. It is a **proposal only** until this architecture is owner-approved and the migration receives a separate schema/security review. It has not been applied to production. Do not run it against production as part of architecture freeze.

Required schema invariants:
- Foreign keys prevent orphan account/niche mappings.
- Account identity references the exact canonical existing ID and existing pinterest_credentials row.
- Single-operator ownership is the selected model; do not invent human actor IDs.
- One active primary niche per account, enforced by a database constraint/index and transaction-safe repository logic.
- Learning snapshots reference a valid account+niche assignment.
- JSON settings/metrics are bounded and validated; no arbitrary unbounded blobs.
- Timestamps use timezone-aware UTC semantics.
- No secret/token/affiliate credential columns.
- Restrictive deletion behavior preserves historical mapping, attribution and learning evidence.
- Migration is additive, reversible by a separately reviewed rollback plan, and has no implicit production backfill.

## 6. Security and authorization model

- Reuse the existing fail-closed API-key dependency for current service-to-service access.
- Every account-scoped endpoint must validate the account is connected and authorized for the caller before reading or mutating its profile/mappings.
- Do not expose decrypted credentials from the vault to API response models, logs, exceptions or tests.
- Use parameterized SQL and transaction boundaries for mapping changes and primary assignment.
- Enforce tenant/account scoping in repository methods, not only in route-level filters.
- Do not add public endpoints for registry writes.
- Audit state changes without recording secrets or affiliate destination URLs.
- Until a real multi-user identity/tenant model exists, describe the current API-key model honestly: it is service authentication, not proof of distinct human ownership. Do not claim tenant isolation beyond what code enforces.

## 7. Explicitly out of scope / deferred

- Rewriting or replacing Model 1.
- New publisher, scheduler, credential vault, publication ledger, raw analytics pipeline, media host or workflow engine.
- Production DB migration/backfill during development.
- Live Pinterest Pin/Board creation during tests.
- OAuth reconnect, refresh forcing or credential rotation for Model 2 tests.
- Pinterest `ads:read`, audience insights, paid ads or advertising-account operations.
- Predictive ML, global learning, autonomous strategy changes or automatic budget allocation.
- Autonomous multi-account publishing/fan-out until its account/board limits and recovery model are approved.
- Personal Browser / UCOS browser integration or Modern Living Hub coupling.
- Automatic Amazon affiliate link construction or invented Associates tracking IDs.
- Importing AGPL-3.0 code.

## 8. Frozen implementation order — gates are sequential

**Do not skip ahead. Do not begin the next phase until the current phase is verified and recorded.**

| Order | Phase | Deliverable | Exit gate |
|---:|---|---|---|
| 0 | Architecture freeze | Owner-approved baseline, reuse matrix, scope, data flow, security and phase order | Explicit owner approval; this document marked FROZEN. |
| 1 | Existing capability inventory | Exact route/function/schema/test map for every reused Model 1 component; identify only genuine gaps | No duplicate capability proposed; inventory cross-checked against current mainline. |
| 2 | Schema review | Review migration 013, constraints, account ownership, nullability, indexes, rollback and data retention | Static tests + disposable PostgreSQL migration/invariant tests; separate approval before any production migration. |
| 3 | Domain contracts | First inventory existing project validators/types; assess suitable verified open-source validation/timezone utilities; add only missing domain contracts for account IDs, niche slug, timezone, assignment state and primary selection | Reuse assessment recorded; unit/boundary tests; no DB/provider calls. |
| 4 | Repository layer | First inventory existing DB/repository abstractions and compatible open-source persistence utilities; add only missing transaction-safe account/niche/profile/mapping persistence; vault existence check remains read-only and token-safe | Reuse assessment recorded; mocked repository tests + disposable PostgreSQL integration tests; cross-account isolation proven. |
| 5 | Protected registry API | Inventory existing route/auth/schema tooling and verified open-source API components; add only missing explicit onboarding and CRUD/list endpoints with account-scoped authorization | Reuse assessment recorded; API auth tests, unauthorized/cross-account denial tests, no provider writes. |
| 6 | Niche context integration | Reuse existing workflow/content pipeline and any suitable verified open-source adapters; pass validated niche context without forking core workflow | Workflow regression tests prove existing Model 1 path remains unchanged when niche context absent. |
| 7 | Niche analytics projection | Reuse existing analytics pipeline and verified open-source SQL/aggregation utilities where suitable; derive account+niche descriptive aggregates from real raw analytics and explicit attribution | Reuse assessment recorded; SQL/integration tests for attribution, missing metrics, period boundaries, deduplication and account isolation. |
| 8 | Read-only dashboard | Display profiles, mappings and evidence-backed aggregates | Protected read-only API/UI tests; no side effects. |
| 9 | Account-aware scheduling design | Separate design review for account/board routing, quotas, idempotency keys, uncertainty and recovery | Written design + adversarial tests; no live scheduler until separately approved. |
| 10 | Release readiness | Exact-head CI, security review, migration rehearsal, deployment/rollback plan and owner sign-off | Explicit release approval; production actions remain separately authorized. |

## 9. Verification standard

For each phase record:
- exact commit and worktree;
- changed files and why each is necessary;
- existing code reused (file/function/table/test references);
- tests run and exact result;
- tests not run and reason;
- security/account-isolation review;
- confirmation no real Pin/Board, production mutation, OAuth change, external image hosting or deployment occurred.

Never label source presence as runtime verification, local tests as CI, CI as production deployment, or deployment health as end-to-end business success.

## 10. Current checkpoint — 2026-11-08

- Architecture freeze has been requested by the owner. This document is being established before further implementation.
- Preliminary additive migration 013, static migration tests, disposable-PostgreSQL integration test source and earlier foundation notes already exist in this isolated worktree. They are **draft artifacts**, not approved/production-applied functionality.
- Previously completed static checks: Python AST parsing, migration filename/order and additive-SQL assertions, and `git diff --check`.
- Runtime pytest and PostgreSQL integration tests have not been executed in this worktree because required dependencies/PostgreSQL tooling were unavailable. Do not report them as passing.
- No Model 2 API/repository integration has been implemented in this checkpoint.
- No commit, push, PR, merge, production DB migration, Render deployment, OAuth operation, Pinterest write, Pin or Board creation occurred.
- The owner backup worktree and clean production snapshot remain separate and must not be modified.
