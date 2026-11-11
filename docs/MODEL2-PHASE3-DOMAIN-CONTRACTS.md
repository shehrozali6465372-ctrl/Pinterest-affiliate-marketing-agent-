# Model 2 Phase 3 — Domain Contracts

**Status:** IN PROGRESS
**Started:** 2026-11-09
**Architecture authority:** `docs/MODEL2-FOUNDATION.md` (FROZEN)
**Phase 2 acceptance:** `docs/MODEL2-PHASE2-SCHEMA-REVIEW.md`, section 18

## 1. Scope and boundary

Phase 3 defines pure, bounded domain input contracts for Model 2 account identity, niche taxonomy, account profile metadata, account–niche assignments, and timezone/region values. This phase must not access PostgreSQL, the credential vault, Pinterest, OAuth, external providers, or the publishing gateway.

The contracts do not authorize a route, repository, migration, scheduler integration, or production operation. Repository-level primary-niche concurrency and account authorization remain Phase 4 responsibilities.

## 2. Existing capability and reuse inventory

| Need | Existing project capability | Decision |
|---|---|---|
| Typed request/domain validation | Pydantic v2 already used throughout the FastAPI application | Reuse Pydantic; no new validation dependency |
| IANA timezone validation | `app/affiliate_scheduler.py` uses stdlib `zoneinfo.ZoneInfo` and `ZoneInfoNotFoundError` | Reuse stdlib `zoneinfo`; no timezone package |
| Supported regions | `app/trends.py` (`SUPPORTED_REGIONS`) and `app/trend_visuals.py` (`REGIONS`) support `US` and `GB+IE` | Reuse exact existing region codes; do not invent more |
| Canonical Pinterest account identity | Credential vault stores existing `account_id`; migration 013 constrains `pinterest:<user_id>` | No reusable application-level validator found; add pure Model 2 validator matching DB constraint |
| Niche slug | Migration 013 constrains lowercase ASCII kebab-case | No shared application-level slug validator found; add pure Model 2 validator matching DB constraint |
| Account/niche/assignment states | Existing scheduler states are unrelated lifecycle contracts | Define narrow Model 2 Literal state sets; do not reuse scheduler states |
| Primary assignment uniqueness | Migration 013 partial unique index enforces one active primary per account | Keep database uniqueness authoritative; paused mappings may retain the primary flag but do not count toward active-primary uniqueness |

Dependency assessment: existing Pydantic and Python standard library cover the required contracts. No additional package is justified. No third-party source or license import is needed.

## 3. Implemented pure contracts

New module: `app/model2_domain.py`.

- `AccountId`: bounded canonical `pinterest:<user_id>`; rejects missing prefix, empty suffix, whitespace and additional colon segments. This mirrors migration 013's account ID check.
- `NicheSlug`: lowercase ASCII kebab-case, 1–120 characters; rejects uppercase, underscores, repeated/leading/trailing hyphens, whitespace and non-ASCII characters.
- `AccountProfileInput`: canonical account ID, bounded optional display name, `active|paused` status and valid IANA timezone (default `UTC`).
- `NicheInput`: slug, nonblank bounded display name, bounded description, existing `US|GB+IE` region taxonomy and `active|archived` status.
- `AccountNicheAssignmentInput`: canonical account ID, positive strict integer niche ID, `active|paused` status, primary flag and settings object. A paused assignment may retain its primary flag for later reactivation, but only an active primary mapping participates in the unique-primary invariant. Settings must remain empty because migration 013 deliberately does not yet define a versioned settings schema.
- All models reject unknown fields. Validation is pure and side-effect free.

## 4. Invariants that remain outside Phase 3

- Whether an account exists and is connected must be checked through a metadata-only, token-safe credential-vault/repository operation in Phase 4. The domain validator does not prove connection or authorization.
- Whether a niche exists or is active is a repository invariant.
- At most one active primary niche per account is enforced by the Phase 2 partial unique index and must be preserved transactionally in Phase 4. A per-request Pydantic model cannot prove a cross-row invariant.
- Pausing an account, archiving a niche, or pausing an assignment must not delete historical attribution or learning evidence.
- No automatic reassignment of existing accounts or historical publications.
- No account/niche settings beyond the currently approved empty object.
- Region expansion requires a coordinated change to the existing trend contract and the Model 2 schema; it is not silently accepted here.

## 5. Verification

New tests: `tests/test_model2_domain.py`.

Latest isolated local run on 2026-11-09:
- `PYTHONPATH=. /root/.venvs/model2-pg16/bin/pytest -q tests/test_model2_domain.py`: **22 passed**.
- Python compilation for the new module and test file: PASS.
- `git diff --check`: PASS.
- No database or provider calls were made; no credentials were read; no Pin or Board was created.

## 6. Phase 3 exit review checklist (completed; evidence in section 7)

The following review was completed before Phase 3 closure:
1. Cross-check every domain constraint against migration 013 and existing Model 1 validators.
2. Review whether display-name normalization, strict input types, timezone aliases and account-ID syntax match intended API semantics.
3. Add edge/boundary tests for any agreed refinements.
4. Run the new tests together with existing Model 2 migration/static tests; PostgreSQL is not needed for pure domain tests.
5. Record security review confirming no secrets, token material, caller ownership or provider state are inferred by these models.

No repository persistence, API routes, DB migration, OAuth action, Pinterest write, production DB action, PR, merge or deployment is part of Phase 3.


## 7. Final contract and security review — 2026-11-09

**Phase 3 — CLOSED / VERIFIED.**

### Contract/schema cross-check

- Canonical account ID format, 10–200 character bounds, no whitespace/extra colon segments and `pinterest:` prefix match the Phase 2 SQL check. The contract accepts Unicode non-whitespace user-ID characters because the SQL check does not restrict the suffix to ASCII.
- Niche slug uses the same lowercase ASCII kebab-case grammar as migration 013. The application contract additionally bounds input slugs to 120 characters; the SQL column itself is TEXT without a matching maximum, so repository/API callers must use this domain contract consistently.
- Profile display name and timezone bounds match SQL. The application additionally validates IANA timezone existence using the already-used stdlib `zoneinfo`; SQL only bounds the string length.
- Niche display name nonblank/120 and description 2000 bounds match SQL. The input contract trims display name and description before persistence.
- Supported region codes exactly match the existing Model 1 `US` and `GB+IE` trend contract and migration 013.
- Profile, niche and assignment state Literals match the SQL allowed values.
- Assignment settings remain exactly empty, matching the deliberately closed JSONB constraint in migration 013.
- A paused assignment may retain `is_primary=true`; only active primary rows participate in the approved partial unique index. This schema nuance is covered by a regression test.
- Positive strict integer niche IDs and strict booleans/strings prevent accidental Pydantic scalar coercion at the domain boundary.

### Security review

- All contracts are pure Pydantic validation; no imports or calls to database, credential vault, Pinterest, OAuth, HTTP clients, publishing gateway or scheduler.
- No credential, token, ciphertext, API key, cookie, affiliate URL, human actor ID or ownership claim is represented in these input models.
- An `account_id` is only a validated identifier. It does not prove the account exists, is connected, or is authorized for the caller. Phase 4 repository/service code must independently enforce those checks without decrypting or returning token material.
- The one-active-primary-across-mappings rule remains enforced by the database unique index and must be handled transactionally in Phase 4; one request model cannot establish a cross-row invariant.
- Extra fields are forbidden and model validation is strict; no hidden owner/tenant identity is inferred.

### Final verification evidence

- Focused Model 2 suite: **37 passed, 9 skipped**. The 9 skips are PostgreSQL integration tests intentionally gated on `TEST_DATABASE_URL`.
- Full repository suite: **204 passed, 27 skipped, 1 warning** in 22.05s.
- Skips were intentional database integration gates: Model 2 PostgreSQL tests (9), publication recovery tests (15), token refresh integration (1), and PB10 database-pool recovery integration (1). No `DATABASE_URL`, `TEST_DATABASE_URL` or `PB10_TEST_DATABASE_URL` was supplied; no database was contacted.
- The single non-blocking warning is Starlette's deprecation notice for using `httpx` with `starlette.testclient`. It is an existing test-stack compatibility warning, not a Model 2 contract failure; no unrelated dependency migration was made.
- New runtime test dependencies were installed only into the isolated `/root/.venvs/model2-pg16` environment from the repository's existing `requirements.txt`. No dependency manifest or lockfile was changed.
- Python compilation and `git diff --check` passed.

### Phase 3 exit decision

All Phase 3 exit gates are satisfied: reuse assessment recorded, pure typed contracts implemented, boundary tests passed, existing Model 1 regression suite passed, and security/account-authorization boundaries documented. **Phase 3 is formally closed.**

**Next phase: Phase 4 — Repository Layer.** Before implementing, inventory existing DB connection/transaction abstractions and the credential-vault query boundary. Add only the missing transaction-safe Model 2 repositories. Account-existence verification must be metadata-only and must not call `get_pinterest_credential`, because that function may decrypt and refresh OAuth tokens. No production DB, migration, provider call, Pin/Board write, PR, merge or deployment is authorized by this Phase 3 closure.
