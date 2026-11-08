# Model 2 Phase 8 — Read-only Dashboard

**Status:** IN PROGRESS — read-only extension implemented; local dashboard regression tests pass; disposable PostgreSQL CI gate pending.
**Started:** 2026-11-09
**Architecture authority:** docs/MODEL2-FOUNDATION.md (FROZEN)
**Prerequisites:** Phases 6 and 7 closed.

## 1. Existing dashboard reuse inventory

- Existing dashboard is implemented in app/dashboard.py and mounted by app/main.py.
- Existing routes: GET /dashboard, POST /dashboard/session, DELETE /dashboard/session, GET /dashboard/api/overview.
- Authentication: existing shared APP_API_KEY exchanged for a signed 12-hour HttpOnly, Secure, SameSite=Strict session cookie. This is service-key authentication, not distinct human identity or tenant isolation.
- Existing UI is a single embedded HTML/CSS/JS dashboard with 30-second read refresh. No separate frontend project or frontend dependency exists in this repository.
- Existing overview is read-only and currently shows one global/selected schedule, job counts, upcoming/recent jobs, publication counts and product count.
- Existing tests: tests/test_dashboard.py covers login requirement, secure session cookie and wrong-key rejection.
- Phase 1 inventory confirms dashboard is global schedule-oriented, not account/niche scoped.

## 2. Phase 8 implementation boundary

Extend the existing dashboard only:
- Add a separate authenticated GET /dashboard/api/model2 endpoint.
- Add a read-only Model 2 panel in the existing dashboard HTML.
- Show account profile display name, canonical account ID, profile status and timezone.
- Show each assigned niche's display name/slug, region, niche status, assignment status and primary marker.
- Show attributed successful publication count, learning snapshot count, latest snapshot period and descriptive metric totals from existing Model 2 snapshot rows.
- Preserve NULL/unknown metrics visibly as "Unknown"; never render missing as zero.
- Show explicit "Model 2 schema not installed" / unavailable state when migration 013 is absent, without breaking the existing Model 1 operations dashboard.
- The endpoint must never return OAuth token material, affiliate destination URLs, API keys, cookies, session signatures or other secrets.
- The dashboard remains a single-operator view behind existing session authentication. Do not claim multi-user isolation.

## 3. Query and data rules

- Read only model2_account_profiles, model2_account_niches, model2_niches, model2_publication_niche_attributions and model2_learning_snapshots.
- Use parameter-free read-only SQL with no mutation, provider calls or credential vault decryption.
- Keep one row per account+niche assignment. Use correlated/LATERAL aggregates or separate grouped subqueries to avoid fan-out multiplication between attribution and learning snapshots.
- Account profile without a niche assignment should still be visible.
- Paused accounts, paused assignments and archived niches remain visible with explicit state labels; dashboard does not hide historical or paused configuration.
- Learning aggregates are account+niche scoped and derived only from existing persisted snapshots. Dashboard does not trigger projection or refresh.
- Query must remain compatible with pre-013 databases: use to_regclass check and return schema_available=false when Model 2 tables are absent.
- Existing /dashboard/api/overview behavior and Model 1 schedule panel must remain unchanged.

## 4. Required tests

- Auth: unauthenticated Model 2 dashboard endpoint returns 401; session authentication remains unchanged.
- Data: profile with no niche, one account with multiple niches, primary marker, paused/archived state, attributed publication count, snapshot count/latest period and NULL metrics.
- Security: response contains no token/secret/affiliate URL fields; exact account+niche aggregation; no cross-account leakage.
- Compatibility: absent migration tables produce a safe unavailable state, not 503 or failure of Model 1 overview.
- Side effects: no publisher, scheduler, generation, OAuth, or DB write path called.
- PostgreSQL: use disposable DB fixture after migration 013; verify query result and account/niche grouping.
- Existing dashboard and Model 1 API regression suite.
- GitHub Actions exact-head disposable PostgreSQL run and fixture cleanup gate.

## 5. Exit gate

Phase 8 remains IN PROGRESS until protected read-only API/UI tests, PostgreSQL dashboard tests, existing dashboard regression tests, full CI and cleanup gate pass on exact feature-branch head. No production DB, migration, live Pin/Board, provider/OAuth action, PR, merge or deployment is authorized.


## 6. Implementation checkpoint — 2026-11-09

Implemented in the isolated Model 2 feature worktree:

- Reused app/dashboard.py and the existing signed dashboard session; no new frontend, auth scheme, package or dashboard service.
- Added authenticated GET /dashboard/api/model2. It uses the existing dashboard session guard and returns only non-secret account/niche metadata and persisted evidence.
- Added a read-only Model 2 panel to the existing embedded HTML dashboard, with account profile, canonical account ID, account status, timezone, niche, region, niche/assignment status, primary marker, attributed successful publication count, snapshot count and latest period/metrics.
- NULL or absent metrics render as Unknown, not zero. Account profiles with no niche assignment remain visible. Paused accounts/assignments and archived niches remain visible with explicit states.
- SQL uses correlated LATERAL aggregates to avoid attribution × snapshot fan-out multiplication. It reads only profile, mapping, niche, attribution, publication and persisted snapshot tables; it does not invoke projection, publishing, scheduling, generation, OAuth or credential decryption.
- A to_regclass preflight returns schema_available=false when migration 013 is absent, preserving the existing Model 1 dashboard on pre-migration environments.
- Added tests for authentication, pre-013 compatibility, non-secret response shape, read-only SQL, HTML panel, and PostgreSQL account/niche grouping with multiple niches, no-niche profile, paused/archived states and evidence metrics.
- Dedicated CI workflow includes the new dashboard unit tests, existing dashboard regression tests and PostgreSQL dashboard integration test through the existing Model 2 PostgreSQL test module.

### Local evidence

- Focused dashboard tests: 7 passed, 1 non-blocking Starlette/httpx TestClient deprecation warning.
- Full local suite: 279 passed, 49 skipped, 1 warning. PostgreSQL integration cases are skipped locally because database environment variables are unset; no database was contacted locally.
- Python compilation passed. CI YAML target validation and git diff --check pending final pre-push check.
- Exact-head disposable PostgreSQL CI remains pending. Phase 8 is not closed until it passes.

No production DB/migration, provider/OAuth action, real Pin/Board, PR, merge or deployment occurred.
