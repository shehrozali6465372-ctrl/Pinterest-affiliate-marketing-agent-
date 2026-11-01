# Function audit coverage matrix and findings — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0
Audit documentation HEAD when authored: 15992be65e14372de9c1d13b2f6d73a8fc60c91c
Review type: static GitHub source review. No production code was changed; only audit documentation was added.

## Coverage snapshot

| Scope | Inventory | Audit coverage | Runtime proof |
|---|---:|---|---|
| Python files in app/, scripts/, tests/ | 30 | Definition inventory enumerated | Not applicable |
| Production source files (app + scripts) | 13 | 94 FN-prefixed records, including class/model/helper records; module call graph reviewed | No live production calls |
| Test modules | 17 | 119 top-level test functions have individual TEST records; nested fakes/fixtures/helpers covered in grouped helper reviews where present | Tests not run in this audit |
| SQL migrations | 8 | All 8 reviewed statement-by-statement | Not applied |
| GitHub Actions workflows | 5 | All 5 reviewed step-by-step | No workflow dispatched |
| Audit Markdown documents | 234 | 233 records excluding index | GitHub docs commits verified |
| Duplicate audit IDs | 0 | No duplicate FN-/TEST- record IDs in filename inventory | N/A |

### Test-function records by module

| Module | Individual test records |
|---|---:|
| tests/test_api.py | 40 |
| tests/test_database_pool_recovery.py | 6 |
| tests/test_database_pool_recovery_integration.py | 2 |
| tests/test_deepseek_completion.py | 8 |
| tests/test_deepseek_failure_diagnostics.py | 1 |
| tests/test_deepseek_http_diagnostics.py | 3 |
| tests/test_diagnostics.py | 7 |
| tests/test_image_base64.py | 3 |
| tests/test_learning.py | 4 |
| tests/test_pinterest_readonly.py | 5 |
| tests/test_postgres_publication_recovery.py | 4 |
| tests/test_provider_retry.py | 5 |
| tests/test_publish_reconciliation.py | 14 |
| tests/test_publish_recovery_state_machine.py | 4 |
| tests/test_token_refresh.py | 6 |
| tests/test_workflow_persistence_recovery.py | 5 |
| tests/test_workflow_recovery.py | 2 |
| **Total** | **119** |

Helper/fake/fixture definitions are discussed in TEST-HELPERS-* documents. These grouped reviews explain helper roles and limitations; they are not separate one-file-per-every-nested-method records.

## Production call graph

- FastAPI app/lifespan → main routes + diagnostics router + learning router + workflow router.
- Hub credential callback → credential ingest service key → credential vault → AES-GCM encrypt → Neon upsert.
- Trusted refresh caller → refresh route → decrypt refresh credential → Pinterest OAuth token endpoint → encrypt/upsert rotated token.
- Product/content API → product persistence → DeepSeek content generation → content-version persistence.
- End-to-end publish route → idempotency lookup → credential vault → Pinterest account GET → board list/create → Cloudflare Workers AI image → DeepSeek content → atomic product/content persistence → publication reservation → Pinterest POST /pins → persist confirmed Pin ID or unknown state.
- Learning Loop → credential vault → confirmed publications filtered by account → Pinterest analytics GET per Pin → metric validation → analytics snapshot upsert → aggregate descriptive metrics; no ML training.
- Publication recovery → DB status read → read-only board pagination + Pin detail GET → operator-supplied evidence → guarded unknown-only DB transition.
- Shutdown → close psycopg pool.

## Prioritized findings

1. **P1 — Refresh is not automatically invoked by normal API request paths.** Refresh is a separate service-key route; workflow and Learning Loop directly use stored access tokens. An external caller or explicit refresh-on-expiry design is required.
2. **P1 — End-to-end route may create a board before later provider/persistence failure.** _ensure_board can POST /boards before generating content and persisting the product. This is a real side effect even when no Pin is created.
3. **P1 — Uncertain Pinterest writes require operator reconciliation.** Never blindly retry after transport/5xx/missing-ID/persistence uncertainty. Keep unknown rows visible and alerted.
4. **P2 — Learning Loop is real analytics ingestion, not ML training.** It persists metrics and descriptive aggregates; model_trained is false.
5. **P2 — Product research/extraction from affiliate URL is absent in audited baseline.** Product name/details are mandatory caller inputs; URL is a destination, not a source of verified product facts.
6. **P2 — Provider diagnostics may be billable.** POST /diagnostics/run calls Cloudflare Workers AI and DeepSeek; it does not create a Pin or product row but can consume provider usage.
7. **P2 — Pinterest account operation route includes create_board/create_pin outside publication ledger.** If used, this parallel write path can bypass the idempotency/publication state machine and should be constrained or retired.
8. **P3 — Legacy publication rows have NULL account_id after migration 007.** They are excluded by account-filtered Learning Loop until safely backfilled from authoritative records.
9. **P3 — Board listing helper checks at most first 100 boards.** No pagination is implemented in _ensure_board; matching board on a later page may be missed and a duplicate board could be created.

## What this audit proves — and does not prove

**Proves from source:** the recorded application commit contains the described routes, persistence calls, encryption design, provider calls, retry/state handling, migrations, workflows and test assertions. All 119 top-level test functions have individual documentation records; all 8 migrations and 5 workflows have static reviews.

**Does not prove:** current Render deployment runs this source; current Neon schema matches migrations; GitHub secrets are present; Pinterest OAuth refresh works against the live account; DeepSeek/Cloudflare provider access currently works; the opt-in disposable PostgreSQL integration tests ran; the scheduled Learning Loop completed; or any real Pin was published. Fake HTTP/database tests do not prove live external behavior.

No test suite was executed as part of this audit. The PostgreSQL recovery integration test terminates a backend session and was deliberately not run. No diagnostics POST was called because it may incur provider charges. No publish endpoint, OAuth mutation, production DB mutation, migration, deployment, merge or secret change was performed.

## Audit completion classification

- Repository/module inventory: COMPLETE.
- Individual top-level test function documentation: COMPLETE (119/119).
- Test helper/fixture review: COMPLETE at grouped module level; nested fake methods are not all split into individual files.
- SQL migration and workflow static review: COMPLETE.
- Production call graph and prioritized source findings: COMPLETE at system/module level.
- Every production definition's standalone line-by-line explanatory record and full test-to-definition assertion mapping: PARTIAL. Existing FN records include exact source excerpts/identities, but several remain generic or marked UNVERIFIED and need deeper per-definition write-up before claiming exhaustive line-by-line completion.
- Runtime/CI verification: NOT PERFORMED in this audit.

This report deliberately does not label the entire function-by-function task fully complete while the per-definition explanatory records remain partial. The source review is complete enough to identify the principal architecture and operational risks, but exhaustive per-function documentation and runtime verification are separate remaining work.