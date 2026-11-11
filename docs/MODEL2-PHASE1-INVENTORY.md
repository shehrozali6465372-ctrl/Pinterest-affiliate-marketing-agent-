# Model 2 — Phase 1 Existing Capability Inventory

**Status:** Phase 1 source inventory completed; runtime/production claims are not implied.
**Inspection date:** 2026-11-08
**Repository:** `/root/restore-staging/Pinterest-Agent-model2-worktree`
**Branch / base:** `feat/model2-open-source-reuse` / `785efd99849627062c1fff8504d21ca91abfee8e`
**Method:** source, SQL migrations, route declarations, dependencies and tests inspected locally. No production system was queried or changed.

## 1. Executive result

Model 1 already contains most foundational infrastructure needed by Model 2. Do not rebuild it.

Verified by source inspection:
- FastAPI application and protected route dependencies.
- Pydantic request validation and settings.
- PostgreSQL access, connection pool and migration runner using Psycopg 3.
- Encrypted Pinterest credential storage and account-keyed lookup.
- Canonical publishing gateway and publication ledger/idempotency.
- Product/content version persistence and workflow generation checkpoints.
- Draft-first scheduler, schedule/job/source persistence and account-level active-schedule uniqueness.
- Pin-level organic analytics ingestion and descriptive Learning Loop.
- Read-only dashboard and Pinterest diagnostics/verification.
- Direct Base64 media submission; no new image host is required.

Model 2 gaps that remain:
1. No dedicated non-secret account profile/ownership registry.
2. No niche taxonomy or explicit account–niche mapping API/repository.
3. No metadata-only connected-account existence lookup in the credential vault; existing credential getters decrypt and return access-token material to trusted internal callers.
4. No persisted, auditable niche attribution for products/content/publications/raw analytics.
5. No account+niche analytics projection built from explicitly attributed real source snapshots.
6. Existing scheduler permits only one active schedule per account, and has no niche dimension. Do not enable multi-niche scheduling until the account/niche/board quota and idempotency design is separately proven.
7. Existing dashboard shows one globally selected schedule and is authenticated by a shared service API key; it is not a per-account tenant dashboard.
8. Current API key is service authentication, not a distinct human/tenant ownership identity. A multi-user authorization model is not established by the current code.

The initial Model 2 migration and two test files already exist as untracked draft artifacts in this worktree. They are not implemented API/repository functionality, have not been runtime-tested here, and have not been applied to production.

## 2. Existing capability map — reuse

| Area | Existing source/schema | Existing tests/evidence | Decision |
|---|---|---|---|
| HTTP API framework | `app/main.py`; FastAPI routers in `workflow.py`, `learning.py`, `affiliate_scheduler.py`, `dashboard.py`, `diagnostics.py`, `trends.py`, `trend_visuals.py` | `tests/test_api.py`, `test_diagnostics.py`, scheduler/dashboard tests | Reuse FastAPI and existing route/dependency patterns. |
| Request/domain validation | Pydantic models in `main.py`, `workflow.py`, `learning.py`, `affiliate_scheduler.py`; `app/pin_limits.py` | API, scheduler, Pin-limit and workflow tests | Reuse Pydantic validators and shared limits; do not add another validation framework. |
| Timezone validation | `ZoneInfo` / `ZoneInfoNotFoundError` in `app/affiliate_scheduler.py` | `tests/test_affiliate_scheduler.py::test_schedule_input_rejects_invalid_timezone` | Reuse Python standard-library `zoneinfo`; no third-party timezone package needed. |
| PostgreSQL connection/pooling | `app/database.py:get_pool`, `connection`, `run_migrations`, `close_pool`; Psycopg 3 pool | `tests/test_database_pool_recovery.py`, integration tests | Reuse the existing connection abstraction and transaction support; do not add an ORM solely for the registry. |
| Existing account identity / credentials | `migrations/004_create_pinterest_credentials.sql`; `app/credential_vault.py` | `tests/test_token_refresh.py`, credential-related API tests | Reuse canonical `account_id` and encrypted vault. Do not create a second credential table. |
| Pin publishing | `app/publishing_gateway.py`; `app/database.py:begin_publish_attempt/finish_publish_attempt`; `pin_publications` | `tests/test_manual_publish_gateway.py`, `test_publishing_gateway_contract.py`, publication recovery/reconciliation tests | Reuse the one gateway and ledger exclusively. |
| Products/content | `app/database.py` product/content functions; migrations 001/002/005/011 | `tests/test_api.py`, content history/workflow persistence tests | Reuse existing product/content entities. No duplicate content store. |
| Generation workflow | `app/workflow.py`, `app/content_generation.py`, `app/media_generation.py`; migration 012 reservation/checkpoint table | `tests/test_workflow_persistence_recovery.py`, API/workflow tests | Extend existing workflow context only after registry ownership is complete. |
| Scheduler | `app/affiliate_scheduler.py`; migration 009 schedule/source/job tables | `tests/test_affiliate_scheduler.py` | Reuse existing scheduler and queue. No new scheduler/worker. |
| Raw analytics | `app/learning.py`; migration 006 `pin_analytics_snapshots`; publication/account linkage in migration 007 | `tests/test_learning.py`, `tests/test_diagnostics.py` | Reuse raw snapshots and live ingestion. Do not duplicate raw Pin analytics. |
| Dashboard | `app/dashboard.py`; session cookie and read-only overview endpoint | `tests/test_dashboard.py` | Reuse existing dashboard; add account/niche views only after authorization contract is designed. |
| Diagnostics / read-only Pinterest operations | `app/diagnostics.py`, protected publication verification in `app/main.py`, Pinterest client helpers | `tests/test_pinterest_readonly.py`, API and diagnostics tests | Reuse read-only calls; no Pin/Board writes in tests. |
| Media transport | Existing generated-image Base64 path and Pinterest media source | `tests/test_image_base64.py`, `test_publishing_gateway_contract.py` | Preserve direct Base64. No Cloudflare Images or other external image hosting. |

## 3. Route and security inventory

Current route families:
- `/workflow/*`: protected by existing API-key dependency.
- `/learning-loop/*`: protected by existing API-key dependency.
- `/affiliate-scheduler/*`: protected by scheduler API-key dependency.
- `/diagnostics/*`: protected by API-key dependency.
- `/trend-intelligence/*` and `/trend-visuals/*`: protected ingest-key/API-key patterns.
- `/products/*` and publication operator routes: protected by API-key dependencies.
- `/integrations/pinterest/credentials`, `/integrations/pinterest/refresh`, and analytics integration: service credential-ingest key.
- `/dashboard/*`: signed short-lived session derived from the shared API key; dashboard data is read-only.
- `/health`: intentionally public liveness endpoint.

Security limitation for Model 2:
- Existing service API key is shared and does not identify separate human users or tenant ownership.
- Existing learning request accepts an account ID and fetches that account's stored credential; the current shared service key is not a per-account user authorization model.
- Model 2 must not claim end-user account isolation until a real caller-to-account authorization mechanism exists.
- Account-scoped repository methods must enforce scope, not rely only on route filtering.

## 4. Database facts and boundaries

Existing relevant tables:
- `pinterest_credentials`: unique `account_id`, encrypted access/refresh token ciphertext, connection status and expiry metadata.
- `pin_publications`: unique `(content_version_id, board_id)`, nullable `account_id` for legacy records, status and confirmed Pin ID.
- `pin_analytics_snapshots`: raw Pin-level metrics keyed by Pin and period; references publication.
- `affiliate_publishing_schedules`: account ID, timezone, board name, date window and daily cap.
- `affiliate_product_sources` / `affiliate_pin_jobs`: schedule-owned source and job queue.
- `workflow_generation_reservations`: idempotency/lease/checkpoint persistence.

Important constraints:
- Legacy publication rows can have NULL account ownership; never infer their account or niche.
- One active schedule per account is enforced by `affiliate_one_active_schedule_per_account_idx`.
- Schedule daily limit is bounded 1–5 and schedule window is bounded to 30 days.
- Scheduler currently has no niche_id column or niche-level quotas.
- Raw analytics have no niche attribution column/relationship.
- Existing credential table does not expose a dedicated safe metadata-only account existence repository function.
- No account profile or niche mapping tables exist in migrations 001–012.

Draft-only Model 2 proposal already present:
- `migrations/013_model2_account_niche_registry.sql` proposes `model2_niches`, `model2_account_profiles`, `model2_account_niches`, and `model2_learning_snapshots`.
- `tests/test_model2_registry_migration.py` contains static additive/schema assertions.
- `tests/test_model2_registry_postgres.py` contains disposable-PostgreSQL fixture/tests for mapping constraints and account separation.
- These artifacts were authored before the architecture-first freeze. They require Phase 2 schema review and alignment before they are accepted. They do not prove repository/API behavior.

## 5. Open-source-first assessment

No new external library is justified by the current inventory. The existing stack already provides the required primitives:

| Need | Existing verified option | License evidence | Decision |
|---|---|---|---|
| API routing/dependencies/OpenAPI | FastAPI already required and used | Official repository declares MIT: https://github.com/fastapi/fastapi/blob/master/pyproject.toml | Reuse; do not replace or add another API framework. |
| Typed validation / request schemas | Pydantic already required and used | Official repository declares MIT: https://github.com/pydantic/pydantic/blob/main/pyproject.toml | Reuse; no additional schema-validation library needed for initial domain contracts. |
| PostgreSQL driver/pooling | Psycopg 3 already required and used | Project PyPI metadata lists LGPL-3.0-only: https://pypi.org/project/psycopg/ | Reuse existing driver; retain LGPL notice/compliance in dependency inventory. No SQLAlchemy/ORM addition justified. |
| OAuth token encryption primitives | cryptography already required and used | Official project declares Apache-2.0 OR BSD-3-Clause: https://github.com/pyca/cryptography/blob/main/pyproject.toml | Reuse existing AES-GCM vault. Do not create another crypto subsystem. |
| IANA timezone validation | Python standard-library `zoneinfo` already used in scheduler | Python standard library; no third-party dependency | Reuse. |
| Slug validation | Pydantic + Python standard-library regex | No extra package needed | Reuse existing validation approach; add only a shared helper if Phase 3 proves a real duplication/gap. |
| SQL constraints/transactions | PostgreSQL + existing Psycopg connection/transaction support | PostgreSQL project ecosystem; existing dependency already in use | Use DB constraints and transactions; no ORM or migration framework replacement. |
| Tests | pytest already declared in `requirements.txt` | Existing project test dependency | Reuse existing tests and CI; local interpreter lacks pytest at this checkpoint. |

Verification limitation:
- Repository requirements specify version ranges, not an exact lockfile. Exact resolved package versions and transitive dependency licenses were not verified in this inspection.
- The license checks above are based on the projects' official metadata/source. They do not replace a complete dependency/SBOM/license scan before release.
- No new dependency has been installed or added.
- No AGPL-3.0 source has been copied. Postiz/Postmill remain architecture references only unless separately approved.

## 6. Genuine Model 2 gaps — no implementation yet

| Gap | Why existing feature is insufficient | Planned phase |
|---|---|---|
| Canonical account profile and ownership/authorization model | Credential rows prove a stored connected credential, not caller-to-account ownership or account operational profile | Phase 2–5 |
| Safe credential metadata lookup | Existing getters decrypt and return token material internally; registry onboarding needs existence/status metadata only | Phase 4 |
| Niche taxonomy and account–niche mapping repository/API | No such tables/routes/domain layer in migrations 001–012 | Phase 2–5 |
| Explicit niche attribution for content/publications | Existing product/content/publication schemas have no niche assignment relationship | Phase 6 schema design/review |
| Account+niche learning projection | Existing Learning Loop stores raw per-Pin snapshots and account-wide aggregates; no explicit niche grouping | Phase 7 |
| Multi-niche schedule policy | Existing schedule is account-scoped with one active schedule/account and no niche/board quota model | Phase 9 design only |
| Account/niche dashboard isolation | Existing dashboard reads one global schedule and uses shared-key session, not per-user account scopes | Phase 8, after auth model |
| Production-ready multi-tenant auth | Shared API key is service authentication only | Must be designed before claiming tenant isolation; may require a separately approved identity provider/auth architecture |

## 7. Phase 1 exit assessment

**Source inventory:** completed for the core account, publishing, scheduler, analytics, dashboard, auth, database and dependency boundaries.

**Not completed / not claimed:**
- Full test suite execution: NOT RUN. `python3 -m pytest --version` returned `No module named pytest` in the active system interpreter.
- Disposable PostgreSQL tests: NOT RUN.
- Exact dependency resolution/SBOM scan: NOT RUN.
- Production deployment/DB verification: NOT performed in this phase.
- External open-source candidates beyond existing stack: no additional package was required by the current gap inventory; do not add one speculatively.

**Phase 1 conclusion:** Do not build Model 1 systems again. Proceed to Phase 2 schema review only after recording that the account registry, niche registry/mapping and niche learning projection are genuine gaps. Review draft migration 013 carefully before accepting it. No Model 2 API/repository code should be added during Phase 1.

## 8. Safety confirmation

- No production database mutation or migration.
- No Render deployment, GitHub commit, push, PR, merge or branch switch.
- No Pinterest API write, Pin creation, Board creation, OAuth refresh or token rotation.
- No real credentials or secret values read or printed.
- No image hosting introduced.
- Owner backup worktree and clean production snapshot were not modified.
