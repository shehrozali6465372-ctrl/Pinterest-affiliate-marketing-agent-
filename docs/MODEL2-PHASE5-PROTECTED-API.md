# Model 2 Phase 5 — Protected Registry API

**Status:** IN PROGRESS — routes and local API tests implemented; feature-branch CI verification pending.
**Started:** 2026-11-09
**Architecture authority:** `docs/MODEL2-FOUNDATION.md` (FROZEN)
**Prerequisite:** Phase 4 closed; see `docs/MODEL2-PHASE4-REPOSITORY-LAYER.md` section 8.

## 1. Existing auth and API inventory

| Need | Existing capability | Phase 5 decision |
|---|---|---|
| Shared service API-key authentication | `app/main.py:require_api_key` | Moved the single implementation to `app/auth.py`; main re-exports the same function for existing route compatibility |
| Publication/operator auth alias | `require_configured_api_key` in `app/main.py` | Kept as an alias to the same fail-closed dependency; no second auth implementation |
| Router registration | Existing FastAPI app and `include_router` pattern in `app/main.py` | Add one dedicated Model 2 router |
| Request/domain validation | Phase 3 Pydantic v2 contracts | Reuse `AccountProfileInput`, `NicheInput`, `AccountNicheAssignmentInput` |
| Persistence | Phase 4 repository layer | Route handlers call repositories only; no direct SQL in routes |
| Credential state | Phase 4 metadata-only vault helper | No token decryption, OAuth refresh or provider request in routes |

No new API framework, auth package, database dependency or provider integration was added.

## 2. Protected resource API

All routes are under `/model2` and have a router-level `Depends(require_api_key)` dependency. Authentication is the existing shared `X-API-Key` service key; missing configuration returns 503 and a missing/invalid key returns 401.

| Method | Path | Purpose | Expected success |
|---|---|---|---|
| GET | `/model2/accounts` | List non-secret account profiles for the single operator | 200 |
| GET | `/model2/accounts/{account_id}` | Read one exact canonical account profile | 200 |
| PUT | `/model2/accounts/{account_id}` | Explicitly create/update profile metadata; onboarding requires a connected stored credential | 200 |
| GET | `/model2/accounts/{account_id}/niches` | List assignments for only that account | 200 |
| PUT | `/model2/accounts/{account_id}/niches/{niche_id}` | Idempotently create/update one account–niche assignment | 200 |
| GET | `/model2/niches?include_archived=false` | List active niches by default; optionally include archived | 200 |
| POST | `/model2/niches` | Create a niche taxonomy entry | 201 |
| GET | `/model2/niches/{niche_id}` | Read one niche | 200 |
| PUT | `/model2/niches/{niche_id}` | Replace niche metadata and lifecycle state | 200 |

No delete endpoint exists. Historical registry, mapping and attribution rows are retained.

## 3. Request/response and state rules

- Request bodies reuse the Phase 3 domain contracts; unknown fields and scalar coercion are rejected.
- Account profile PUT requires explicit `status` and `timezone`; its path account ID must exactly match the body.
- Assignment PUT requires explicit `status` and `is_primary`; both path identifiers must match the body.
- Niche PUT requires explicit `status` and `default_region`, preventing omission of default values from silently reactivating an archived niche or resetting its region.
- Niche creation is non-idempotent by slug; duplicate slug returns 409. Account profile and assignment PUT operations are idempotent.
- Account IDs are validated canonical identifiers, not human actors. The shared API key represents the single operator/service boundary and does not claim multi-user or tenant isolation.
- Response models use explicit allowlists with `extra="forbid"`. No token, ciphertext, OAuth scope, username, affiliate URL or secret is part of any Model 2 response.
- Routes call only Phase 4 repository functions. Repository not-found/conflict errors map to 404/409; invalid path/body semantics map to 422; storage failures map to safe 503 responses without raw SQL details.
- Registry GET operations do not trigger credential refresh, analytics ingestion, scheduling, generation or publishing.

## 4. Security and side-effect review

- `app/auth.py` is the single fail-closed implementation used by Model 2 and imported by `app.main`. Existing `require_configured_api_key` remains a backwards-compatible alias.
- No new auth bypass or public write route was introduced.
- Account and niche path/body identity mismatches are rejected before repository calls.
- Account niche reads always use the exact path account ID; repository SQL remains scoped by account ID.
- The API does not accept owner IDs, tenant IDs, OAuth tokens, provider URLs or arbitrary settings.
- No route imports or calls Pinterest, the publishing gateway, OAuth, media generation, scheduler, Learning Loop or affiliate URL handlers.

## 5. Local tests and current evidence

New test module: `tests/test_model2_registry_api.py`.

- Focused API/domain/repository tests: **65 passed, 1 warning**.
- Existing Model 1 API regression suite: **40 passed, 1 warning**, confirming the shared-auth extraction did not break existing route behavior.
- Full repository suite after Phase 5 implementation: **238 passed, 34 skipped, 1 warning** in 21.45s. Database integration tests remain intentionally skipped locally because DB environment variables are unset.
- The 20 API tests cover missing/unconfigured/invalid key, protected routes, exact path/body identity, canonical account ID, explicit lifecycle fields, 404/409 mappings, archived-niche filtering, response allowlists (including fail-closed handling of an injected secret field), account-scoped assignment reads, and no publisher invocation.
- The dedicated GitHub Actions workflow has been expanded to include Model 2 API tests and existing Model 1 API regressions, in addition to disposable PostgreSQL tests.

## 6. Phase 5 exit gate

Phase 5 remains IN PROGRESS until:
1. Local API and full repository test results remain green.
2. Feature-branch GitHub Actions run executes the new API suite and existing Model 1 API regressions successfully, alongside PostgreSQL registry tests and cleanup checks.
3. Review exact CI commit and verify no production DB, provider, OAuth or Pinterest writes occurred.
4. Confirm route responses and OpenAPI expose only approved non-secret fields.

Next after Phase 5: Phase 6 — Niche Context Integration. Reuse existing workflow/content pipeline; no new workflow engine or publishing path.


## 7. Final CI evidence and Phase 5 closure — 2026-11-09

**Phase 5 — CLOSED / VERIFIED.**

Authoritative GitHub Actions run:
- Run: [42527370397](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42527370397)
- Commit: \`b16511de0fa15d9ac07f5dc2e201eadb231b6d25\`
- Branch: \`feat/model2-open-source-reuse\`
- Result: **127 passed, 0 failed** in the CI test step (1 non-blocking Starlette/httpx TestClient deprecation warning).
- Disposable PostgreSQL 16.15 service was used only by GitHub Actions.
- All 14 numbered migrations were recorded in the fresh database.
- The independent post-test cleanup gate verified zero synthetic Model 2 registry/learning rows and zero synthetic Model 1 analytics/publication/product/content-version rows.
- The ephemeral PostgreSQL service container was stopped and removed.

### Final review

- Every \`/model2\` endpoint is protected by the same fail-closed shared API-key dependency.
- Existing \`app.main.require_api_key\` remains available as an imported alias; \`require_configured_api_key\` is a backwards-compatible alias to the same implementation.
- Existing Model 1 API regression suite passed after authentication consolidation.
- Response models are explicit allowlists with \`extra="forbid"\`; an injected unapproved token field produces a safe response-validation failure and does not expose the value.
- Path/body account and niche identifiers must match; lifecycle fields are explicit on PUT to prevent implicit reactivation/default resets.
- Account-niche listing is scoped to one exact canonical account ID. The API does not claim multi-user/tenant ownership; the API key is service/operator authentication.
- Routes call only Model 2 repositories. No provider, OAuth, Pinterest, publishing, scheduler, image or Learning Loop side effects.
- Local full repository suite: **238 passed, 34 skipped, 1 warning**. Local database skips were intentionally gated; CI executed all PostgreSQL integration tests.
- No Neon/production database, production migration, OAuth/provider operation, Pinterest write, real Pin/Board, PR, merge or deployment occurred.

**Phase 5 exit gates are satisfied. Phase 5 is formally closed.**

**Next: Phase 6 — Niche Context Integration.** Reuse the existing Model 1 workflow and content-generation pipeline. First inspect prompt/content contracts and workflow call sites; only pass a validated optional niche context. The existing Model 1 behavior must remain byte-for-byte/semantically unchanged when niche context is absent. No second workflow engine or publisher.
