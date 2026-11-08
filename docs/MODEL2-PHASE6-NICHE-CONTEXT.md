# Model 2 Phase 6 — Niche Context Integration

**Status:** CLOSED / VERIFIED — 2026-11-09.
**Started:** 2026-11-09
**Architecture authority:** \`docs/MODEL2-FOUNDATION.md\` (FROZEN)
**Prerequisite:** Phase 5 closed; see \`docs/MODEL2-PHASE5-PROTECTED-API.md\`.

## 1. Existing Model 1 path to reuse

- \`app/workflow.py:ProductWorkflowInput\` and \`publish_product_end_to_end\` are the existing end-to-end workflow.
- \`app/content_generation.py:generate_pin_content\` is the existing DeepSeek content-generation implementation, JSON schema validation, retry handling and affiliate disclosure enforcement.
- \`app.database\` already owns generation idempotency/checkpoints, product/content persistence and publication reservation.
- \`app.publishing_gateway.publish_pin\` is the sole controlled Pinterest Pin-write boundary.
- The workflow currently generates for the fixed Model 1 audience: USA, Home Decor & Kitchen.
- Existing direct Model 1 content generation in \`app/main.py\` remains unchanged and continues using \`PROMPT_VERSION\`.

No second workflow, prompt engine, publisher, publication ledger or scheduler will be introduced.

## 2. Optional niche context contract

- Add optional positive \`niche_id\` to the existing workflow request. Omission must preserve the current Model 1 request fingerprint, prompt, generation call arguments, prompt version and gateway call arguments.
- When present, load the active account+niche assignment through an exact-account repository query. The account profile, assignment and niche must all be active.
- Use only approved niche metadata: niche ID, slug, display name, description and supported region (\`US\` or \`GB+IE\`).
- Treat the niche description as untrusted descriptive data, not instructions. Product facts and visible image evidence remain the only sources for product claims.
- Include the exact niche context snapshot in the workflow request fingerprint. A changed niche definition under the same idempotency key must not silently reuse a prior generation.
- Use a distinct prompt version for niche-context generation; retain \`pin-content-v1\` for the no-context Model 1 path.

## 3. Publication attribution at the existing gateway

Migration 013 already provides immutable publication-scoped niche attribution. Phase 6 must connect it to the existing gateway, not create another publisher.

- Optional niche ID flows from workflow to \`publish_pin\` to \`begin_publish_attempt\`.
- The gateway reservation transaction validates the exact account profile, active assignment, active niche and connected credential using row locks and metadata only.
- The same transaction reserves the existing \`pin_publications\` row and inserts the immutable \`model2_publication_niche_attributions\` row before the Pinterest network request begins.
- If an existing publication already has attribution, a retry must use the same niche. A different niche is rejected.
- A succeeded/pending/unknown legacy publication without attribution must not be retroactively attributed by a later request. It remains blocked and requires no automatic backfill.
- A failed legacy reservation may receive explicit niche attribution only when the retry supplies an active account+niche assignment; attribution and retry reservation commit atomically.
- If an attributed failed publication is retried after its assignment/profile/niche is paused or archived, the gateway blocks the retry.
- When niche ID is absent, existing Model 1 gateway behavior remains unchanged.

## 4. Failure and concurrency rules

- Missing/paused account assignment, archived niche or disconnected credential returns a safe conflict before Pinterest POST /pins.
- The final gateway check is authoritative; the earlier context lookup is only for prompt preparation and may become stale while providers run.
- Profile/assignment/niche row locks are held through publication reservation and attribution insertion. Concurrent pause/archive waits; once the gateway commits, the immutable attribution records the exact assignment used.
- No new provider calls are introduced for niche metadata. The metadata comes only from the local Model 2 registry.
- The content-generation prompt uses the existing DeepSeek call, same JSON schema, retry policy and disclosure handling.
- No real Pin/Board may be created during tests.

## 5. Required verification

- Unit tests prove the no-context prompt and workflow path retain the exact existing defaults.
- Context prompt tests prove the niche metadata is structured and instruction-like metadata is explicitly treated as data.
- Repository tests prove exact account scoping and active-state checks.
- PostgreSQL tests prove attribution is committed atomically with the existing ledger reservation, legacy successful publications are not backfilled, mismatched niche retries are blocked, inactive assignments cannot reserve a Pin, and the existing publication state machine is unchanged when niche ID is absent.
- Gateway/workflow tests mock all provider and publishing operations; no live Pinterest API request.
- Full Model 1 regression suite must pass.

## 6. Phase 6 exit gate

Phase 6 remains IN PROGRESS until local tests and feature-branch CI pass, including disposable PostgreSQL integration tests and migration-ledger/cleanup verification. No production DB, migration, live provider call, OAuth operation, Pin/Board publication, PR, merge or deployment is authorized by this phase.


## 7. Implementation checkpoint — 2026-11-09

Implemented in the isolated Model 2 feature worktree:

- Added strict bounded NichePromptContext and NICHE_PROMPT_VERSION to the existing DeepSeek generator. The no-context prompt remains the original fixed USA/Home Decor & Kitchen prompt and retains pin-content-v1.
- The workflow accepts optional positive niche_id. With a niche supplied it fetches the exact active account+niche context before any provider call, passes the structured metadata to the existing generator, includes the full context snapshot in the workflow fingerprint, and uses the distinct niche prompt version.
- Niche metadata is serialized as JSON and explicitly treated as untrusted descriptive data in both system and user instructions. Product claims remain limited to supplied product facts and visible image evidence.
- All internal DeepSeek retry paths preserve the same niche context.
- The existing publishing gateway accepts optional niche_id and forwards it to the existing begin_publish_attempt; no alternate publisher was introduced.
- The existing publication reservation transaction locks the account profile, exact account–niche assignment, niche and credential status using FOR SHARE. It validates connected credential state through the existing metadata-only helper. It inserts the existing publication ledger row and immutable niche attribution in the same transaction before the Pinterest POST.
- Existing attributed failed publications retain their niche on retry and revalidate active assignment/credential. Failed legacy publications can be attributed only on an explicit retry with a supplied active assignment. Succeeded/pending/unknown legacy publications without attribution are blocked from retroactive attribution. Different-niche retries are rejected.
- Added workflow/gateway/prompt tests in tests/test_model2_niche_context.py and prompt tests in tests/test_deepseek_completion.py; added exact-account/state and publication-attribution PostgreSQL cases in tests/test_model2_registry_postgres.py.
- Dedicated CI now includes test_model2_niche_context.py and test_deepseek_completion.py in addition to Model 2 repository/API and PostgreSQL tests, plus the existing Model 1 API regression suite and migration/fixture cleanup gate.

### Local evidence

- Focused prompt/workflow/gateway/repository tests: 40 passed.
- Full local repository suite: 256 passed, 43 skipped, 1 warning.
- The 43 skips include database integration tests because DATABASE_URL, TEST_DATABASE_URL and PB10_TEST_DATABASE_URL were unset. No database was contacted locally.
- Python compileall, workflow YAML parsing, required CI target checks and git diff --check all passed.
- Disposable PostgreSQL publication-attribution tests have not yet run. Phase 6 remains open until the feature-branch CI run proves them and the fixture cleanup gate passes.

No real Pin/Board, Pinterest API request, OAuth refresh, production DB/migration, PR, merge or deployment has been performed.


## 8. Final CI evidence and Phase 6 closure — 2026-11-09

**Phase 6 — CLOSED / VERIFIED.**

Authoritative GitHub Actions run:
- Run: 42531360160
- Commit: f8700286cd286a4601bc3d5afcf40500584fafef
- Branch: feat/model2-open-source-reuse
- Result: **162 passed, 0 failed, 0 skipped** in the CI test step; one non-blocking Starlette/httpx TestClient deprecation warning.
- Disposable PostgreSQL 16 service used by GitHub Actions only.
- All 14 numbered migrations recorded.
- Independent post-test cleanup verified zero Model 2 fixture rows and zero synthetic Model 1 analytics/publication/product/content-version rows.
- Ephemeral PostgreSQL service container stopped and removed.

Final gate review:
- No-context Model 1 workflow retains its original fingerprint, prompt, prompt version, generation call shape and publishing gateway call shape; regression tests passed.
- Niche context is optional, exact-account scoped, active-state checked, bounded and treated as untrusted descriptive data.
- Context snapshot participates in the workflow fingerprint; niche prompt has a separate version.
- The existing publication gateway and ledger are reused. Attribution is committed in the same reservation transaction before any Pinterest POST.
- Legacy succeeded/pending/unknown publications without attribution cannot be retroactively attributed. Failed legacy reservation requires an explicit active niche on retry. Mismatched niche retry and inactive assignment/credential are blocked.
- No real Pin/Board, Pinterest API write, OAuth refresh, production DB/migration, PR, merge or deployment occurred.

**Phase 6 exit gates satisfied. Phase 6 is formally closed.**

Next: Phase 7 — Niche Analytics Projection. Reuse raw Model 1 analytics and immutable Model 2 publication attribution. Preserve exact raw source lineage; never fabricate zero for missing metrics. Keep aggregates descriptive/read-only; no predictive ML or autonomous strategy changes.
