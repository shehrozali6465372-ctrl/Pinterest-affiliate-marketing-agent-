

## Authoritative status update — 2026-10-30 20:58 PKT (owner-approved)

- **PB-07 — CLOSED / VERIFIED.** PR #43 merged to main at `016fde8c91224d4915337019771bad37b25b1c94`. Render deployment `dep-dbibdpff3r2c73cipupg` is `live` on that exact commit. Agent `/health` returned HTTP 200. Protected `GET /publications/1/pinterest-verification` returned HTTP 401 without the API key, confirming the route is deployed and access-controlled. GitHub Actions read-only production verification run [41081017678](https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/41081017678) completed successfully; all steps passed, including protected readiness/provider checks and existing publication #1 board pagination/Pin-detail verification. No Pin was published, no production DB write occurred, and no token was rotated. Limitation: this verifies an existing successful publication, not a replay of an actual ambiguous/unknown-state production incident.
- **PB-13 — CLOSED by explicit owner approval on 2026-10-30.** The owner accepted closure after the DeepSeek retry/backoff and sanitized stage/provider telemetry work was merged and deployed (PRs #38–#42; deployed retry/backoff baseline included in PR #42), and the safe production provider smoke verification had passed. Historical intermittent 503 root cause was not conclusively isolated; record this as an accepted residual/known limitation, not as a proven root cause. Do not reopen unless a new reproducible 503 or material provider regression is observed.
- **PB-05 — ONLY REMAINING OPEN TECHNICAL BLOCKER.** Genuine Pinterest refresh-token rotation and encrypted persistence have not been verified in production. Do not force expiry or rotate the live token just to test; complete a safe naturally-due refresh and verify only non-secret metadata/account access.
- **PB-03, PB-04, PB-06, PB-07, PB-10, PB-13 — CLOSED. PB-12 — DEFERRED**, because the analytics dataset is not yet sufficient for predictive model training; this is not a release blocker.
- **PB-08 — HUMAN REVIEW / release sign-off**, tracked separately from the single remaining technical blocker; it is not counted as an open engineering PB blocker in this status summary.
- **Release gate:** one remaining technical blocker: PB-05. No new Pin publishing is authorized by this status update.
# Context append — PB-05 Remote Desktop Commander continuation (2026-10-28)

- Remote Desktop Commander device `bb54f029-ff20-4907-ad1f-8b963b1958c1` came online; local repo `/root/Pinterest-affiliate-marketing-agent` was inspected. Local branch is `fix/pb06-pinterest-analytics-shape`, not `main`; do not assume the working tree is the deployed version or push it directly.
- Targeted refresh regression tests: **5 passed**, one existing Starlette/httpx deprecation warning. Combined API + token-refresh tests: **44 passed**, one same warning. Full current local suite: **66 passed**, one same warning.
- Production Agent `/health`: HTTP 200. Protected `/readiness` and Pinterest diagnostics returned HTTP 401 when called without the API key, which confirms auth protection; no secret values were printed.
- The protected local config `/root/.config/pinterest-agent/.env` exists with permissions `0600`; key names (never values) confirmed: `APP_API_KEY`, `DATABASE_URL`, `PINTEREST_CREDENTIAL_INGEST_KEY`, `PINTEREST_TOKEN_ENCRYPTION_KEY`. Pinterest OAuth client ID/secret are not present in this file. The file contents are not exposed in chat.
- PB-05 remains **OPEN — production token refresh lifecycle not yet verified**. Do not expose or copy secrets, force expiry, alter production expiry metadata, or publish a Pin. Next safe route needs authenticated server-side execution with the existing configured Hub/Agent secrets, then verify rotation/persistence by metadata and account lookup.
- No source code was changed by this check; no production tokens were rotated; no Pin or board was created.

## Verified continuation update — 2026-10-29 (Remote Desktop Commander)

- Online device `bb54f029-ff20-4907-ad1f-8b963b1958c1` was used. Original branch `fix/pb06-pinterest-analytics-shape` was preserved unchanged; an isolated branch `fix/pb06-analytics-forward-port` was created from current `main` to forward-port the PB-06 analytics parsing fix.
- PR #30 (`ops: add safe manual production provider diagnostics`) merged to `main` at `def34e272b846b491d8f76b69abfb77790e6e893`. Exact-head Python Tests and Python CI passed. The manual workflow was dispatched as run `40845099954`; GitHub reports `success`, and all steps including configuration and authenticated non-publishing diagnostics succeeded. It enforces no Pin/board creation and safe output. This run may incur DeepSeek/Cloudflare usage. No new Pin was published.
- PR #30 review-loop reviewer selection is now persisted as Codex (`chatgpt-codex-connector`, trigger `@codex review`). The `@codex review` trigger was posted, but latest loop fetch has no Codex review threads yet; do not fabricate an AI review. There are no actionable review threads recorded by the review-loop fetch.
- The local PB-06 implementation initially conflicted with current `main` in `app/learning.py` and `tests/test_learning.py`. Conflicts were resolved on isolated `fix/pb06-analytics-forward-port`; original branch/worktree was left untouched. Full local suite: **66 passed**, 1 existing Starlette/httpx TestClient deprecation warning. `git diff --check` passed.
- PR #31 (`fix: handle Pinterest Learning Loop analytics summary shapes`) was opened, both exact-head checks passed, merge state became `CLEAN`, and it was merged to `main` at `871315d780ecc6c6c66e14d84792d3863cae0243`. Post-merge Python CI and Python Tests on that exact SHA both succeeded.
- Live Agent `/health` returned HTTP 200 repeatedly. Hub `/api/health` returned HTTP 200 with `agent_configured`, `pinterest_client_id_configured`, and `redirect_uri_configured` true.
- Neon read-only inspection reconfirmed 1 credential row, 1 successful publication row, and 2 analytics snapshots. Latest stored snapshot for Pin `1069323505300280780` reports real metrics: impression 3, pin_click 1, outbound_click 1, save 0 for 2026-09-28 through 2026-10-28. Earlier snapshot for prior period had zeroes. `model_trained=false` remains correct.
- **Deployment:** Render deployment `dep-dbhgngpsrm7s73fqdsc0` was triggered after verifying the previous deployed SHA was stale. Render confirmed it reached `live` with commit `871315d780ecc6c6c66e14d84792d3863cae0243`. Agent health then returned HTTP 200 repeatedly. Current code commit is therefore confirmed deployed.
- PB-05 (real token refresh), PB-07 (live uncertain-publish recovery), PB-10 (pool recovery/root cause), and PB-13 (intermittent DeepSeek 503 diagnosis) remain outstanding per authoritative 2026-10-29 production report. No production token expiry was forced or mutated. No new Pin was published.

### Additional verified Learning Loop — 2026-10-29 09:06 UTC

- Ran GitHub Actions workflow `Pinterest Learning Loop` on current deployed `main` SHA `871315d780ecc6c6c66e14d84792d3863cae0243`; run `40847008820` completed successfully.
- Real protected `POST /learning-loop/run` returned `ok=true`, `pins_checked=1`, `snapshots_saved=1`; period `2026-09-29` through `2026-10-29`. Aggregate metrics: impressions 3, saves 0, outbound clicks 1, save rate 0.0, outbound click rate 0.3333. `learning_status=analytics_ingested_descriptive_evaluation_only`; `model_trained=false` is correct.
- Neon read-only count after the run: 3 `pin_analytics_snapshots`, 1 `pin_publications`, 1 `pinterest_credentials`. No publishing endpoint called; no new Pin or board created.
- Latest live Agent `/health` and Hub `/api/health` still return HTTP 200. Protected `/readiness` with no key returns 401 as expected; no credentials were provided in that probe.
- Latest production app commit is deployed and healthy at `871315d780ecc6c6c66e14d84792d3863cae0243`. `PB-06` now has verified real snapshot persistence after the parser fix, though ongoing analytics reconciliation/longitudinal sufficiency still matters. Predictive ML remains deferred.

### Deep root-cause investigation — PB-05 / PB-07 / PB-10 / PB-13 (2026-10-29)

Scope: read-only source/test/history inspection through Remote Desktop Commander and authenticated GitHub CLI. No production mutation was attempted. No real Pin was published; no token expiry was forced.

- Local verification: `PYTHONPATH=. .venv/bin/pytest -q` => **66 passed, 1 existing Starlette/httpx deprecation warning**. Running pytest without `PYTHONPATH=.` failed collection because this repo's `app` package was not on the import path; this was an invocation/environment issue, not a test regression.
- PB-05 — **implemented but live lifecycle unverified**. `POST /integrations/pinterest/refresh` requires `X-Credential-Ingest-Key`, loads encrypted refresh credentials from Neon, rejects malformed/expired refresh-token expiry before contacting Pinterest, rotates access/refresh credentials and preserves the existing refresh token if Pinterest omits a replacement. Unit tests cover successful mocked rotation, omitted-rotation preservation, expired-token preflight, malformed expiry, and auth rejection. Correction after follow-up: the earlier check inspected only the repository `.env` and current process environment. A protected local config file exists at `/root/.config/pinterest-agent/.env` with mode `0600`; its values were not read or exposed. The protected file was parsed locally for key names only; values were never printed. A fresh GitHub Actions diagnostic successfully used server-side GitHub secrets. Actual token refresh remains unverified because the local file does not include Pinterest OAuth client ID/secret and the refresh endpoint requires those two fields. Do not create/copy secrets into chat or force expiry. Next proof: invoke via already-secret-backed server/workflow with an account whose refresh token is naturally due, then compare only non-secret expiry/update metadata and repeat read-only account lookup.
- PB-07 — **failure handling implemented/test-covered; live recovery not established**. `app/workflow.py` and `app/main.py` mark ambiguous timeout/5xx/missing Pin-ID outcomes `unknown` and block duplicate retry (`409` / `502` path); `app/database.py` serializes publication attempt reservation with transaction advisory lock and blocks `pending`, `unknown`, and `succeeded` states. Regression tests cover persistence failure not calling `/pins` and ambiguous publish setting `unknown`. This investigation did not run a live uncertain-publish injection because it risks a duplicate real Pin. Safer next gate is a controlled production-like disposable/test account or provider stub that proves: request sent -> timeout/connection loss -> persisted `unknown` -> same version/board retry blocked -> operator checks board -> explicit reconciliation path. Current code shows no automatic reconciliation transition for `unknown`; manual reconciliation/runbook is therefore part of operational recovery.
- PB-10 — **live root cause still unproven; checkout hardening exists**. `app/database.py:get_pool()` lazily creates one `psycopg_pool.ConnectionPool` (min 1/max 5) using `ConnectionPool.check_connection` on checkout to reject idle/stale connections after Neon disconnects; `close_pool()` closes and resets the global pool at shutdown. The installed psycopg_pool implementation checks connection viability with an empty query under temporary autocommit. There are currently no targeted tests found for stale-connection checkout replacement, pool exhaustion, reconnect after pool closure, or Neon idle disconnect. Recent authenticated `SELECT 1` / DB diagnostics succeeded, but one healthy probe cannot prove recovery. Add isolated unit tests with a fake/controllable pool and a non-production integration test using a short-lived DB connection to verify stale checkout/reconnect and pool state after close; production verification needs a sanitized time-series of pool wait/connect failures and server-side disconnects. No pool reset or database mutation was done here.
- PB-13 — **exact current 503 cause not proven; prior causes were partially addressed**. Historical merged PR #18 documented a live non-publishing DeepSeek generation failure with `JSONDecodeError`, caused by truncated JSON while reasoning/thinking consumed a 1,200-token budget; it disabled thinking, raised the output budget and added sanitized failure classification. PR #20 added one retry for transient HTTP 429/5xx and transport errors. Current `app/content_generation.py` retries HTTP 429/5xx once, logs only HTTP status/provider error code and exception type, and distinguishes envelope JSON/model JSON/schema failures without logging keys, prompts or full responses. The safe production smoke workflow `40845099954` on `def34e272b846b491d8f76b69abfb77790e6e893` returned HTTP 200 and `deepseek_multimodal_generation.ok=true`; thus DeepSeek works at least for that sample, but this does not establish the cause of intermittent 503s on other requests. Current diagnostics collapse DeepSeek exceptions to `deepseek_multimodal_completion_failed`, which loses response-class detail in the public summary. Next action: capture the next failing stage's sanitized log tuple (`status`, provider error `type/code`, retry attempt, request duration, `finish_reason`, content length/response content-type where applicable), correlate with request ID/time and upstream provider status page, and avoid logging request data or secrets. Only apply a second retry/backoff or classify as upstream quota/model overload after that evidence; no blind change to model/settings.
- GitHub review-loop tooling: the `gh-review-loop` skill was read as required, but the plugin scripts/preferences are not installed on this remote device (`GGRL_PLUGIN_ROOT` discovery returned empty). Therefore this pass used authenticated, read-only `gh` PR/run history rather than claiming a plugin-owned review/thread fetch. No reviewer feedback was fabricated, and no PR was pushed/re-requested.
- Current status stays: PB-05 open (real refresh evidence), PB-07 open (live uncertain-outcome recovery/reconciliation evidence), PB-10 open (no targeted pool recovery test or production failure evidence), PB-13 open (intermittent upstream 503 root cause unknown). Existing code/tests and current successful smoke test are evidence of partial implementation only, not blocker closure.


### Follow-up verification — 2026-10-29 (authorized Remote Desktop Commander)

- Re-ran local tests with the existing protected config left private: baseline before additions `66 passed`; added four focused pool lifecycle tests and one sanitized DeepSeek diagnostic failure test. Latest complete local suite: **71 passed, 1 existing Starlette/httpx TestClient deprecation warning**. `git diff --check` passes. New tests are local-only and have not been committed, pushed, or deployed.
- Protected env was inspected only for key names: `APP_API_KEY`, `DATABASE_URL`, `PINTEREST_CREDENTIAL_INGEST_KEY`, `PINTEREST_TOKEN_ENCRYPTION_KEY`; `0600` mode confirmed. No Pinterest OAuth client ID/secret names are present. No secret values printed.
- Fresh safe production diagnostic run `40904239646` on deployed SHA `871315d780ecc6c6c66e14d84792d3863cae0243` succeeded at 2026-10-29 15:42 UTC: DB `SELECT 1`, Pinterest stored credential/account read HTTP 200, Cloudflare image generation passed, DeepSeek Flash structured content generation passed. Explicit workflow summary confirms no Pin/board/product/image persistence, `secrets_returned=false`. Provider usage may be billable.
- Fresh external Neon read-only query via the connected Neon integration: database `pinterest_affiliate`, role `pinterest_app`, `SELECT 1` passed. Credential metadata: account `pinterest:1069323642682526567` connected; access and refresh ciphertext both present; access expiry `2026-11-27T09:26:42Z`, refresh expiry `2026-12-27T09:26:41Z`, last updated `2026-10-28T09:26:42Z`. No tokens decrypted. One successful publication exists; no pending/unknown publication row in current `pin_publications` grouping. Do not treat this as proof of ambiguous-outcome recovery.
- PB-10 made progress locally: four targeted tests cover missing-DB guard, lazy singleton pool config including stale-connection checker, and pool close/reset. They do not simulate real connection drop/replacement or prove production recovery; keep PB-10 open until stronger fake-driver/reconnect integration evidence and production logs exist.
- PB-13 made progress locally: added a regression test confirming the current live diagnostic sanitizer does not surface raw exception details or a token string, while still indicating the DeepSeek diagnostic failure generically. This test documents the current limitation rather than adding provider response status/code context. The fresh successful sample still does not explain intermittent 503s; keep PB-13 open.
- PB-05 remains open: actual local config lacks client ID/secret inputs required by `/integrations/pinterest/refresh`. Do not attempt a refresh with fake or guessed values; no token changed and no expiry forced.
- PB-07 remains open: no real Pin was published and no ambiguous-publish fault injection was performed. Current DB publication table contains only a succeeded row, but code still lacks an automatic safe transition from `unknown`; do not close the blocker.
- Current local worktree: only `CONTEXT.md`, `PB03-STATUS.md`, and two new test files are modified/untracked. No app source changed. No push or deployment occurred.


### Continuation checkpoint — 2026-10-30 02:20 PKT

- Remote Desktop Commander connection recovered. Worktree status is confirmed; branch remains `fix/pb06-analytics-forward-port`, HEAD `1292516` (`fix learning loop analytics response parsing`). No push, commit, or deployment was made during this continuation.
- Full local suite after additional test coverage: **78 passed, 1 existing Starlette/httpx deprecation warning**; `git diff --check` and `python -m compileall -q app tests` passed.
- Added local-only tests: four pool lifecycle tests in `tests/test_database_pool_recovery.py`, one sanitized diagnostic failure test in `tests/test_deepseek_failure_diagnostics.py`, four publication state-machine tests in `tests/test_publish_recovery_state_machine.py`, and one DeepSeek HTTP 503 retry/provider-code sanitization test in `tests/test_deepseek_completion.py`. The additional tests run no real provider calls and create no Pins.
- PB-07 source review: `begin_publish_attempt()` transaction-advisory-locks `(content_version_id, board_id)` and refuses retry when a matching row is `pending`, `unknown`, or `succeeded`; only `failed` is eligible for another attempt. New deterministic tests confirm this fail-closed state behavior. Do not add auto-retry/reconciliation transitions to `unknown` without a verified board/provider lookup that can prove whether a Pin exists. No production record mutation or publish injection was done. Live DB currently has only one `succeeded` publication row, so production ambiguous recovery remains unverified.
- PB-10 tests now additionally check `connection()` delegates checkout through the pool context manager and propagates lease exceptions. Still no Docker engine/local Postgres server in the environment and no real connection-drop replacement test; PB-10 remains open.
- PB-13 test now confirms HTTP 503 is retried once, provider `type`/`code` is logged in a bounded field, and response message/key are not logged. Latest production smoke succeeded on the prior run, but intermittent real 503 still needs correlated provider/server telemetry and request timing; PB-13 remains open.
- PB-05 remains open: local protected `.env` has no Pinterest OAuth client ID/secret inputs required by the refresh endpoint. Existing access token expiry is 2026-11-27 and refresh expiry is 2026-12-27; no refresh was triggered and no expiry was changed.
- Worktree changes: `CONTEXT.md`, `PB03-STATUS.md`, `tests/test_deepseek_completion.py` modified; `tests/test_database_pool_recovery.py`, `tests/test_deepseek_failure_diagnostics.py`, `tests/test_publish_recovery_state_machine.py` untracked. No application source file modified. Keep all four blockers open pending their stronger evidence gates.


### PB-07 continuation — PR #32 verification checkpoint (2026-10-30)

- Remote Desktop Commander used device `bb54f029-ff20-4907-ad1f-8b963b1958c1`. Branch `fix/pb06-analytics-forward-port`, HEAD `f1d17cc8a0a1adf60afcecadcce3acfafbd9071c`; worktree clean. PR #32 remains OPEN.
- Implemented `GET /publications/{publication_id}` (read-only DB inspection) and `POST /publications/{publication_id}/reconcile`, both using the Agent API-key guard. Database reconciliation takes an advisory lock and row lock, accepts only status `unknown`, and requires explicit operator evidence. `succeeded` requires the operator-verified Pin ID; `failed` must omit a Pin ID and means the operator confirmed absence after exhaustive board verification. Evidence is recorded in `response_metadata.reconciliation`. No Pinterest API requests are made by these endpoints.
- Added `tests/test_publish_reconciliation.py` and `docs/PB-07-PUBLISH-RECOVERY.md`. The runbook requires reading every page of the correct board’s Pins list, verifying a candidate by direct Pin read, leaving status `unknown` on any lookup error/incomplete pagination/ambiguity, and not retrying blindly.
- Exact-head GitHub Python Tests run `40965255116` and Python CI run `40965255272` both passed for `f1d17cc`; Python CI uses a disposable PostgreSQL 16 service and only `TEST_DATABASE_URL`. Local suite: **91 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**. `python -m compileall -q app tests` and `git diff --check` pass.
- **PB-07 remains OPEN.** Reconciliation is in PR #32 and isolated PostgreSQL CI passes. On 2026-10-30, Codex review completed for exact head `66ffe9ec3dc5e02a843f39a0020258225b44b9d2` with receipt “Didn't find any major issues”; no inline findings or review threads were returned. This is an AI review, not human/operator sign-off. Local suite on this device rerun: **91 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**; `.venv/bin/python -m compileall -q app tests`, `git diff --check`, and clean-worktree check passed. Exact-head GitHub Python CI run `40965841448` and Python Tests run `40965841513` both succeeded. PR #32 metadata confirms `open`, `merged=false`, `mergeable=true`, head `66ffe9e`; base/main remains `871315d780ecc6c6c66e14d84792d3863cae0243`. Render service `pinterest-affiliate-marketing-agent` has `autoDeploy=yes` on commits to `main`; do not merge without a deliberate deployment decision. No production deployment, production Neon mutation, Pinterest write, Pin/board creation, or token rotation occurred during this checkpoint.

### PB-13 continuation — sanitized DeepSeek failure telemetry (2026-10-30)

- Created separate PR #33 from current main to keep this work isolated from PB-07 publication recovery: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/33
- Commit efe6e379c952e45d3452de01ce5be6cf59077a5e adds bounded HTTP failure telemetry for DeepSeek: HTTP status, sanitized provider type/code, attempt number, elapsed milliseconds, response content type/byte count, and sanitized provider request ID. It never logs request headers, API keys, prompt contents, or response bodies.
- Added a mocked 503-then-success regression test verifying one retry, useful correlation metadata, and no leakage of a fake secret or response message.
- On the remote device, full suite on main plus the change: 67 passed, 1 existing Starlette/httpx deprecation warning. python -m compileall -q app tests and git diff --check passed. No real provider request or Pinterest write was performed.
- Posted @codex review on PR #33; review result is pending. PR #33 is open and has not been merged. No Render deployment was triggered.
- PB-13 remains OPEN: instrumentation improves the next incident's evidence but does not yet identify the root cause of intermittent production HTTP 503s. Wait for exact-head CI and review, then correlate real sanitized failure logs with provider request ID/time and provider-side status.
- The PR #32 branch remains separate at 66ffe9e; its two local-only status-file edits are preserved on that branch and have not been pushed. No production state was changed.


### Continuation checkpoint — PB-13 credential-redaction fix (2026-10-30)

- PR #33 updated commit: `23e15ecb95735108666ba6c8336006d928a0500c` on branch `fix/pb10-stale-connection-recovery-tests`. Fix redacts the configured LLM credential from provider error code, Content-Type, and request-ID metadata before logging or returning sanitized values.
- Added regression coverage where the fake provider reflects the configured credential in all three metadata fields and the response message. Assertions confirm the credential is absent from logs and `ContentGenerationError`.
- Local full suite: **68 passed, 1 existing Starlette/httpx deprecation warning**. Focused DeepSeek tests: **6 passed**. `.venv/bin/python -m compileall -q app tests` and `git diff --check` passed.
- Exact-head GitHub checks on `23e15ecb95735108666ba6c8336006d928a0500c`: Python CI run `40968210595` and Python Tests run `40968210581` both succeeded.
- Codex re-review completed on the updated head with **no findings**. The previous P2 finding is no longer reported as unresolved on the new head. PR #33 remains open/unmerged. Do not claim PB-13 closed: instrumentation and credential redaction are improved, but intermittent production 503 root cause is still unverified.
- No live DeepSeek request was performed for this fix. No production Neon mutation, Pinterest write, Pin/board creation, token rotation, or Render deployment occurred.
- PB-10 remains OPEN: current pool tests verify lifecycle/configuration only and do not prove recovery after a real connection drop. Next safe engineering task is isolated stale-connection replacement coverage using a controlled non-production test, without injecting a failure into production Neon.


### PB-10 PR #34 CI troubleshooting checkpoint — 2026-10-30

- PR #34 head `a1631c6` initially failed CI because a tool-execution footer was included after the Python test file. Head `a5214e1` also failed because prose checkpoint notes were mistakenly appended into the Python test. This was an authoring/write-target error; no application runtime code changed.
- Corrective commit `25fa037c8b325891e27a4995bed990bcb0b5826b` rewrote the GitHub test file to Python-only source. Exact-head CI must be checked again before considering PR #34 valid.
- The isolated Neon fault-injection experiment remains successful: on the dedicated child branch, backend PID termination was followed by a successful pooled query on a different PID and `SELECT 1`. Focused local tests previously passed 7/7.
- No merge or deployment. Do not push or merge the local PB-07 branch because it retains a local context edit and is separate from PR #34.


### Final continuation status — 2026-10-30

- PR #32: latest documentation checkpoint commit `2952cae4873846e250d241a6eaed30e803fa6baf`; Python Tests + Python CI pass; Codex review completed with no findings.
- PR #33: credential redaction fix commit `23e15ecb95735108666ba6c8336006d928a0500c`; Python Tests + Python CI passed; Codex re-review completed with no findings. PB-13 remains open for actual intermittent production 503 root-cause evidence.
- PR #34: `fix/pb10-disposable-pool-recovery`, latest test-source head `25fa037c8b325891e27a4995bed990bcb0b5826b`. Python Tests run `40970940524` and Python CI run `40970940526` both succeeded. The integration test was checked by fetching the exact GitHub file and confirming the tail is Python-only. Codex status remains running at last status query; a new comment requested reconciliation of review status. No inline review threads exist so far.
- PB-10 disposable Neon integration: manually terminated backend PID on child branch; next pooled query succeeded on a different PID, with `SELECT 1` successful. Targeted pool integration + unit tests passed **7/7** locally. This is strong isolated recovery evidence, but PR #34 is not merged/deployed.
- Render service is confirmed configured to auto-deploy commits on `main`; latest live deploy remains `871315d780ecc6c6c66e14d84792d3863cae0243`. Agent `/health` returned HTTP 200 with `{"status":"ok","service":"pinterest-affiliate-model-1"}` after the free-service wake-up timeout. New PB-10 code is not in Render.
- PR #34 has not been merged. No Render deploy was triggered. No production PostgreSQL sessions were killed; no production DB data modified; no Pinterest write, Pin/board creation, or credential rotation occurred.
- Remaining blockers: PB-07 operator board-verification/release gate; PB-10 PR review/merge/deployed verification (isolated backend recovery proved); PB-13 real intermittent-503 root cause; PB-05 real token-refresh lifecycle. Do not claim these blockers closed solely from unit/CI success.


### PB-10 strict URI guard follow-up — 2026-10-30

- Codex review for PR #34 found two safety issues in the opt-in backend-termination test. First, keyword-format DSN could bypass host validation; corrected to accept only the exact dedicated Neon test URI. Second, libpq URI query overrides such as `?host=prod...` or `?dbname=production` could change the effective target; corrected by rejecting routing/database override keys and allowing only a narrow query-key allowlist.
- Added regression coverage for keyword DSNs, wrong hosts, `host` query override, and `dbname` query override. Current PR #34 head is `6e5809825c47c0e6f5887ecc2f6173daaf5f4d7d`; Python Tests run `40972143345` and Python CI run `40972143050` both passed.
- Latest Codex review was requested for exact head `6e58098`; status still reads running. Prior two findings are outdated after fixes, but the second thread remains formally unresolved until review reconciliation. No merge/deploy.
- The controlled recovery experiment itself is proven on the dedicated child branch: terminated backend PID was replaced and `SELECT 1` succeeded. PR #34 remains open. Production still runs SHA `871315d780ecc6c6c66e14d84792d3863cae0243`, Render health HTTP 200.


### PB-10 host-routing guard — third review edge case (2026-10-30)

- Codex identified that libpq accepts comma-separated multi-host URI authorities and could fall back to a second host even if the first hostname was allowlisted. Updated the test guard to reject comma-separated authorities and IPv6-bracket authorities, in addition to rejecting keyword DSNs and all routing/database query override keys.
- Added regression assertion for `allowlisted-disposable-host,prod.db.example`. Local focused tests: **7 passed, 1 skipped** (live fault injection remains opt-in); full suite: **92 passed, 4 skipped, 1 existing Starlette/httpx deprecation warning**; `compileall` and `git diff --check` passed.
- Latest PR #34 source commit: `19c2b0c74216470bd7a7ff203c9bddb7874d7b8e`; exact-head Python CI run `40972632926` and Python Tests run `40972633033` both passed.
- The two older P2 threads (keyword DSN and query override) are resolved as outdated. Newest multi-host finding was on prior head `6e58098` and is now outdated after the fix; Codex re-review of `19c2b0c` is still running. Keep PR #34 open until the current-head review finishes.
- Production remains live at `871315d780ecc6c6c66e14d84792d3863cae0243`; live `/health` HTTP 200. No merge/deploy. No production DB session terminated or data modified; no Pinterest write/Pin/board creation/token rotation.



### PB-07 and PB-13 continuation — 2026-10-30

- Neon production database `pinterest_affiliate` on default branch `main` was queried read-only. `pin_publications` has one `succeeded` row and zero `pending`/`unknown` rows. There is no current production ambiguous publication to reconcile. No SQL write was performed.
- PR #32 current branch head is `fc7b5bb3d9630e61d9d91426c82c1d866af5d12d`; local full suite: **91 passed, 3 skipped, 1 existing Starlette/httpx deprecation warning**. Earlier exact code-head CI for `f1d17cc`: Python Tests `40965255116` and Python CI `40965255272` passed. Later branch commits are documentation/status only. PR #32 remains open; do not merge because Render auto-deploys main and release sign-off is not complete.
- PB-07 has isolated PostgreSQL 16 CI proof: `tests/test_postgres_publication_recovery.py` uses only `TEST_DATABASE_URL`, cleans synthetic fixtures, makes no Pinterest calls, and proves durable unknown -> retry blocked -> operator reconciliation for both stubbed present/absent outcomes. CI runs `40965255116` and `40965255272` passed for code head `f1d17cc`. Real Pinterest board pagination remains a runbook/operator read-only procedure, not part of the automated test. Production has no unknown row; keep PB-07 open for deliberate release sign-off and future operator incident handling.
- PR #33 PB-13 branch latest commit `eb9d415c12b93510189d316eb423e10d839ddeb5` fixes a second credential leak path in malformed-success-response retry exhaustion by applying the shared redaction helper to Content-Type metadata. New test reflects the fake configured key in Content-Type. Focused tests **3 passed**; full suite **69 passed**; compileall and diff check pass. Exact-head GitHub CI passed: Python CI run `40976788042` and Python Tests run `40976787907`. Codex review of `eb9d415` remains pending; prior review threads are not yet resolved.
- PB-13 remains open: intermittent production DeepSeek 503 root cause is not yet established; no real provider request was made during this patch. Do not merge/deploy until CI and review are clean and a real sanitized failure can be correlated.
- No production DB mutation, Pinterest write, Pin/board creation, token rotation, or Render deploy.

- Render log review (2026-10-23 to 2026-10-30 UTC): two DeepSeek application events surfaced (JSONDecodeError and schema-invalid retry, both 2026-10-26); no HTTP 503 request log matched `/products/*/content`. This is not proof no provider 503 happened; deployed code lacks the new status/request-ID telemetry. No quota/overload conclusion is supported.
- PB-05 read-only Neon metadata: one connected Pinterest account; both encrypted token blobs exist; access expiry `2026-11-27T09:26:42Z`, refresh expiry `2026-12-27T09:26:41Z`, last update `2026-10-28T09:26:42Z`. No token was decrypted or rotated; no forced refresh was attempted because the access token is not near expiry. PB-05 remains open pending genuine server-side refresh/persistence evidence.


### PB-10 final verification — CLOSED (2026-10-30)

- Live Render deploy `dep-dbhgngpsrm7s73fqdsc0` is at SHA `871315d780ecc6c6c66e14d84792d3863cae0243`; deployed `app/database.py` contains psycopg pool checkout validation via `ConnectionPool.check_connection`.
- PR #34 merged as `77cf19220425619fb041a638e12be13815cb41d4` and adds only an opt-in isolated recovery test. Exact-head CI passed (Python Tests `40973794556`, Python CI `40973794511`); Codex review found no issues on the reviewed test head.
- Disposable Neon child-branch fault injection proved backend replacement: after terminating a pooled backend PID, the next pooled query succeeded on a different PID. The test target guard strictly pins the disposable Neon URI/database and requires secure TLS/channel binding.
- Final production-safe probes passed: Neon main `SELECT 1` returned 1; Render `/health` returned HTTP 200 with the expected service identity. No production session was terminated or data changed.
- No new deployment was required because live SHA `871315d` already contains the runtime recovery checker; PR #34 changed tests only. Do not state `77cf192` is deployed. PB-10 is closed.


### PR #32 mainline synchronization — 2026-10-30

- Synced PR #32 branch `fix/pb06-analytics-forward-port` with main `c1679ca3cb7c1f2ba4f3050cd73b0dbe59abef3b` via merge commit `d1135ed3e9b75e9c1e4ea2e594957f8d471a53db`. Resolved the single `PB03-STATUS.md` conflict by preserving main's PB10 history and re-appending current PB07/PB13/PB05 evidence; CONTEXT.md and the PB10 integration test were preserved.
- PR #32 is open/unmerged and now `mergeable=true`. Exact sync-head Python CI run `40979903928` and Python Tests run `40979903920` both passed. Local full suite: 92 passed, 4 skipped, one existing Starlette/httpx deprecation warning; compileall and diff checks passed.
- No merge to main or Render deployment was performed. PB-07 remains open pending operator/release sign-off; PB-10 is closed; PB-13 and PB-05 remain open.


### PB-07 HTTP + disposable PostgreSQL end-to-end verification — 2026-10-30

- PR #32 received commit `1de70ec16c90de2a7ca4222e583934dd6ebcd75f`, adding `test_operator_http_reconciliation_round_trip_on_disposable_postgres` to `tests/test_postgres_publication_recovery.py`.
- The test runs only when CI supplies dedicated `TEST_DATABASE_URL`; it uses synthetic product/content/publication fixtures, never calls Pinterest, checks both operator endpoints reject missing API key (401), reads persisted `unknown`, confirms retry blocked, reconciles through the authenticated HTTP endpoint, re-reads durable `succeeded` state/audit metadata, and confirms duplicate retry remains blocked.
- Exact-head GitHub CI passed on `1de70ec`: Python Tests run `41041546460`; Python CI with PostgreSQL 16 service run `41041546479`. PostgreSQL CI log: **96 passed, 1 skipped, 1 warning**. Local full suite: **92 passed, 5 skipped** because disposable PostgreSQL is not configured locally; compileall and diff check passed.
- This closes the missing HTTP/API-to-disposable-PostgreSQL integration-test gap. It does **not** prove a real Pinterest incident or live board pagination; the read-only board verification remains an operator runbook procedure. Production still has zero `unknown` rows, so no record was manufactured or reconciled.
- PR #32 remains open/unmerged. Render auto-deploys commits to `main`; no merge/deploy performed. No Pinterest write, Pin/board creation, token rotation, or production DB mutation.


### Continuation — PB-06 production reconciliation and PB-13 telemetry review — 2026-10-30

- PB-06 production Neon read-only verification on project `dry-firefly-39925447`, default branch `br-blue-moon-ar7484zv`, database `pinterest_affiliate`: **4** rows in `pin_analytics_snapshots`; latest fetch `2026-10-30T10:11:18.989Z`; **1** succeeded publication and **0** pending/unknown. This supersedes the stale PB-06 status entry that said zero snapshots. Earlier real Learning Loop run `40847008820` returned `ok=true`, `pins_checked=1`, `snapshots_saved=1` on deployed SHA `871315d`. PB-06 ingestion/persistence is verified; model training remains deferred due insufficient data, not an ingestion blocker. `PB03-STATUS.md` corrected on this branch.
- PB-13 PR #33 head remains `eb9d415c12b93510189d316eb423e10d839ddeb5`; exact-head Python CI `40976788042` and Python Tests `40976787907` passed; Codex review summary `6511445701` reports no findings. Both outdated inline review threads (initial provider metadata redaction and malformed-2xx Content-Type) have now been resolved after confirming the exact-head fixes and fresh review.
- Render logs read-only, 2026-10-23 through 2026-10-30 UTC: no request-log rows matched `/products/*/content` with HTTP 503, no request-log rows matched 5xx, and no content-route request rows were returned. Two app-level DeepSeek events were found on 2026-10-26: `JSONDecodeError` and `content schema invalid; retrying once`. Render HTTP metrics returned an empty data series for this window. This is **insufficient evidence** to identify or exclude an intermittent provider 503; it may mean the relevant event was not captured in retained request logs. The new telemetry patch is still not deployed, so PB-13 remains OPEN pending a real failure correlated with sanitized provider status/request ID/time. No billable provider diagnostic was triggered.
- No PR merge, Render deploy, production DB mutation, Pinterest write, Pin/board creation, or token rotation occurred in this continuation.


### PB-05 refresh-expiry metadata fix — PR #35 (2026-10-30)

- Source review found that the database upsert already uses `COALESCE` to preserve a stored `refresh_token_expires_at` when Pinterest omits the expiry field, but the refresh endpoint response incorrectly reported `null` and passed `None` to the storage helper. The endpoint now explicitly carries forward the previous expiry metadata and returns it in ISO-8601 form.
- PR #35: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/35, branch `fix/pb05-preserve-refresh-expiry`, head `6c764c396b00fcde3d9fe53f1d0035a261fc9286`. Regression test now covers a provider response omitting both refresh-token rotation and refresh-token expiry metadata.
- Focused refresh tests: **5 passed**. Full local suite: **67 passed, 1 skipped**; compileall and diff check passed. Exact-head GitHub Python Tests run `41043514706` and Python CI run `41043514721` both passed. PR is open and mergeable; AI review-loop runtime is not available on the connected device, so no reviewer request was fabricated or manually posted.
- This is metadata-preservation hardening only. No live Pinterest refresh, credential decrypt/rotation, production DB write, Pin/board creation, PR merge, or Render deploy was performed. PB-05 remains OPEN pending a genuine server-side refresh event and read-only confirmation of encrypted persistence/expiry metadata.

### PB-07 follow-up — reopen for live read-only Pinterest verification (2026-10-30)

- PB-07 had previously been closed by explicit owner acceptance of the residual live-board-verification gap. The owner has now asked to fix that gap; **PB-07 is reopened as OPEN until the read-only verification enhancement is deployed and exercised against production**.
- PR #43: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/43, branch `fix/pb07-readonly-board-verification`, current head `ae8268ca0663ba2c36cabb325d3f7f4bb4c191b2`.
- Added protected `GET /publications/{publication_id}/pinterest-verification`: server-side credential decryption, complete board pagination with bookmark validation and bounded page count, stored Pin lookup in the board listing, direct Pin detail verification, sanitized output, and no database state mutation.
- Extended the manual read-only production verification workflow to check existing publication ID 1 by default and assert complete pagination plus stored Pin/detail agreement. This checks a known succeeded publication; it does not manufacture an ambiguous publication or rehearse the unknown-state transition against production.
- Local full suite: **114 passed, 5 skipped**; focused read-only/reconciliation suite: **19 passed**; GitHub Python CI run `41078263644` and Python tests run `41078263788` both passed. Compileall, YAML parsing, and diff checks passed.
- **Still pending:** PR #43 merge and Render deployment, followed by manual execution of the updated read-only production workflow. Local protected encryption key was malformed, so no local live credential use was attempted. No live Pinterest API call, production DB write, Pin/board create, or deployment was performed for this change.
- PB-07 must remain OPEN until deployed read-only board pagination and direct Pin verification succeed. Even after that, production unknown-state recovery remains covered by isolated PostgreSQL/provider-stub tests rather than a real production failure rehearsal.


## PB-05 continuation — refresh lifecycle hardening and test coverage (2026-10-30)

- Inspected the deployed Hub/Agent refresh path. Modern Living Hub's server-side `pinterestOp()` catches one Pinterest/Agent HTTP 401, calls the protected Agent `/integrations/pinterest/refresh` with Hub-held OAuth client credentials and the service ingest key, then retries the original operation once. The Agent refresh endpoint decrypts the stored refresh credential in process memory, exchanges it with Pinterest, and stores rotated access/refresh credentials through the AES-GCM Neon vault. No secret values were read or printed.
- Agent PR #44 merged as `c36bb81043077fafc3f11e01f3fc7d0bca782eee`: adds a disposable PostgreSQL integration test that runs the actual protected refresh endpoint and actual credential vault, with a mocked Pinterest OAuth response. It verifies rotated tokens survive a fresh vault decrypt and the DB stores ciphertext, not plaintext. GitHub Python CI and Python Tests passed on head `4162e4d8803c45cf034a7af78fa2766b01a4de65`. The new Postgres integration test ran in Python CI against the disposable PostgreSQL 16 service; local refresh unit tests: 5 passed, 1 skipped (no local TEST_DATABASE_URL).
- Hub PR #10 merged as `0ebd8f1b3c329fff80011559f9fac919eb17bead`: adds a mocked end-to-end regression where the first read-only Pinterest account lookup returns 401, Hub sends exactly one authenticated refresh request using server-side client credentials, retries the read-only account lookup once, and does not expose the client secret. Pinterest Credential Security workflow passed on head `45df539c332dc2290606d905aa09101f6ad0ba49`.
- These changes improve and test the recovery path; they do **not** constitute a real production token rotation. At the last known metadata check the access token expiry was 2026-11-27 and refresh-token expiry 2026-12-27, so no natural expiry-triggered refresh has yet occurred. Do not force expiry. A live refresh before natural expiry would rotate the production credential and requires explicit owner approval; after it occurs, verify successful Hub account lookup and updated non-secret Neon expiry/updated_at metadata. **PB-05 remains the sole OPEN technical blocker until that live proof exists.**
- No production token was decrypted, sent to Pinterest, refreshed, or rotated. No production DB row was modified. No Pin or board was created or published. Test PRs are test-only; no deployment was needed for these test changes.

---

## Authoritative checkpoint — 2026-11-02 19:39 PKT

This checkpoint supersedes older deployment/CI snapshots above where the same facts conflict. It records evidence inspected on 2026-11-02; it does not authorize additional production side effects.

### Current mainline and production deployments

- Latest application-code commit on `main` at checkpoint time: `23729244497497fa9629b02842e93917b55cc2e6` (Pinterest Pin text-limit enforcement). The context-only documentation update was committed separately as `868324d0571987ade2dfc9913a7435adff41d78b`; the Agent Render deployment remains on application commit `2372924` (the docs update did not create a new Render deployment).
- Agent Render service `srv-dbe6psoae00c73c3nhgg`, workspace `3rd render 3500`: deployment `dep-dbk5jqjbc2fs73eg2280` is **LIVE** on the exact `23729244497497fa9629b02842e93917b55cc2e6` commit. This is deployment evidence, not a claim that every product workflow has passed production E2E.
- Modern Living Hub Render service `srv-dabs358n74is7389jut0`, workspace `Render`: latest inspected deployment `dep-dbjmirrm8hqs73fv18v0` is **LIVE** on commit `d164bcc6462d269abdcb53f57f144f522d148915` (canonical Agent publishing gateway integration).
- Do not touch the separate `Atoz product hub website` Render account/workspace.

### Latest mainline CI — verified

For Agent main HEAD `23729244497497fa9629b02842e93917b55cc2e6`:
- Python tests run `41418811893`: **success**; pytest job and all steps passed.
- Python CI run `41418812084`: **success**; test job and all steps passed.
- Pinterest Learning Loop scheduled run `41436393136`: **success**; protected production endpoint call and configuration checks passed.

Run links:
- https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/41418811893
- https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/41418812084
- https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/41436393136

### Real Learning Loop result — 2026-11-02

The successful scheduled production workflow called the protected `POST /learning-loop/run` endpoint for the connected Pinterest account and returned:
- `ok=true`; `pins_checked=2`; `snapshots_saved=2`.
- Period: `2026-10-03` through `2026-11-02`.
- Real returned aggregate metrics: impressions `15`, saves `0`, outbound clicks `5`, save rate `0.0`, outbound click rate `0.3333`.
- `learning_status=analytics_ingested_descriptive_evaluation_only`; `model_trained=false`.

This verifies a real analytics-ingestion run and two saved snapshots. It does **not** establish a trained predictive ML model or prove revenue/engagement lift. Keep ML training deferred until adequate historical data and time-aware evaluation exist.

### Mainline changes now deployed

- PR #52 / commit `467af321b5eb5eb742514fb40ebbd4c808d077f2`: fail-closed API-key configuration, unknown analytics metrics preserved as null, board pagination, canonical Hub publishing gateway backed by the Neon publication ledger, and Cloudflare image persistence work at that commit.
- PR #53 / commit `b8388eddc1c98b21f79245acc4afe035012fb9f0`: generated image bytes are sent directly to Pinterest as Base64 media; generated workflow image is not persisted to Cloudflare Images. This supersedes the earlier PR #52 Cloudflare Images implementation for generated Pin media.
- PR #54 / main commit `23729244497497fa9629b02842e93917b55cc2e6`: centralized Pin text limits and boundary validation: title 100, description 800, alt text 500; affiliate disclosure remains within the description limit; oversized text is rejected before Pinterest API calls.
- Current Agent mainline deployment is on `2372924`; no claim is made here that a Copco Pin was published by these code changes.

### Current in-progress branch — PR #55

- PR #55, `Phase 1: centralize Pinterest Pin creation boundary`, is **OPEN and DRAFT**, branch `phase1/pinterest-pin-write-gateway`.
- Latest inspected PR head: `be517c9fdb15cd0690b750c4b699b5e9de3d93aa`. It is not merged into `main` and is not part of the Render deployment listed above.
- Scope includes a shared outbound Pin-creation boundary, shared publication-ledger operation, atomic product/content/publication reservation, encrypted Neon credential selection for legacy publishing routes, and fail-closed handling for unknown outcomes.
- PR description reports 143 passed / 6 skipped on an earlier branch commit `d4c75be`; the current PR head `be517c9` still needs its own CI and review. Do not treat earlier test results as exact-head verification.
- API compatibility change: legacy publishing routes require `X-Pinterest-Account-ID` to select the encrypted Neon credential.
- No production DB write, live Pinterest request, AI-provider call, Pin publish, merge, or deployment was reported for this PR. Keep it draft until exact-head checks and review are clean.

### Blocker/status reconciliation

Use this checkpoint and the latest owner-approved status above as the current project status; do not resurrect stale older entries below:
- PB-03, PB-04, PB-06, PB-07, PB-10, PB-13: **CLOSED** according to the owner-approved 2026-10-30 checkpoint and subsequent verified work. PB-06 now also has a successful 2026-11-02 production Learning Loop run with two real snapshots.
- PB-05: **ONLY OPEN TECHNICAL BLOCKER** — a genuine naturally-due production Pinterest refresh-token rotation and encrypted persistence/account-access verification is still pending. Do not force expiry or rotate early.
- PB-12: **DEFERRED**, not a release blocker; insufficient real historical analytics for predictive ML.
- PB-08: human review/release sign-off remains separate from the technical blocker count.
- PB-13 closure was explicitly accepted by the owner on 2026-10-30. Its historical intermittent 503 root cause was not conclusively isolated; preserve this as an accepted residual limitation. Reopen only on a new reproducible provider regression or owner request.
- PB-07 closure verifies the protected read-only check of an existing successful Pin and isolated recovery tests; it is not evidence that an actual production ambiguous-timeout incident was replayed.

### Owner-authorized Copco one-Pin request — 2026-11-02

- Product: Copco 3-Tier Spice Rack Organizer.
- Exact owner-supplied affiliate destination (preserve unchanged): `https://link.amazon/B0iUJm1I4`.
- Previously documented Associates tracking ID: `beautybloo0ff-20`. The short-link redirect and tracking attribution have not yet been independently resolved. Do not append or invent a tag; verify attribution safely where possible.
- Owner approved **exactly one** controlled real production Pin through the Agent E2E workflow. This is not authorization for multiple Pins or recurring publishing.
- The evidence inspected for this checkpoint does not establish a confirmed publication result for this Copco request. Before any further create-Pin call, reconcile the publication ledger and Pinterest board read-only. If the outcome is pending/unknown or ambiguous, do not retry; use the documented operator reconciliation path. Do not create a duplicate.
- No additional Pin is authorized by this checkpoint. Never expose secrets or token plaintext.

### Next execution order

1. Keep PR #55 isolated; run and inspect exact-head CI/review before any merge.
2. Preserve the existing one-Pin authorization. Read-only reconcile whether the Copco request already has a publication-ledger row / Pinterest Pin before considering any create request.
3. If no attempt exists and all preflight gates pass, execute no more than the one already-approved controlled Pin. Persist and verify the actual Pinterest Pin ID and publication ledger result.
4. Continue PB-05 only through a naturally due, secret-backed server-side refresh; verify non-secret expiry/update metadata and account read. Do not force expiry.
5. Continue real analytics ingestion; do not claim ML training until data sufficiency and evaluation gates pass.

### Safety and evidence rules

- No deployment, merge, credential rotation, production DB mutation, billable generation, or additional Pin publishing is authorized merely by this context update.
- Never log or store APP_API_KEY, DATABASE_URL, Pinterest tokens, OAuth client secrets, Cloudflare tokens, or other secret values in this file.
- Preserve user changes and untracked tests in local worktrees. Do not reset, overwrite, commit, or push the protected root checkout without explicit authorization.
- Report facts as verified only when supported by a specific run, deployment, API response, or source/test inspection. Distinguish implementation, CI success, production deployment, and real production E2E as separate gates.

## Owner-confirmed publication status — 2026-11-04

- **Vtopmart Pinterest Pin — COMPLETED / GREEN.** The owner confirms the Pin has been published. The project checkpoint also records the Vtopmart publication ledger as completed. Treat this publication task as complete; do not publish a duplicate Pin. This status update records completion only and does not authorize any additional Pinterest publishing.


## Phase 11 operational closeout — 2026-11-04

- Phase 11 is **CLOSED for operational execution**. This closeout accepts one condition-based deferred verification: PB-05 natural Pinterest OAuth token refresh.
- Owner confirmed by screenshots that branch protection was saved for both repositories' `main` branches. Agent required checks are `test` and `pytest`; Hub required check is `credential-security`. PR-required, status-check, up-to-date-branch, conversation-resolution and no-bypass settings are enabled; force-push/deletion are disabled. This is owner/screenshot-confirmed. GitHub API branch-protection read-back was unavailable (403), so do not call it API-independently verified.
- Agent PRs #55, #56 and #58 are merged; Hub PR #11 is merged. PR #58 records owner-confirmed Vtopmart Pin publication as completed/green. Do not publish a duplicate.
- Neon backup and isolated restore rehearsal are completed; do not repeat.
- **PB-05 — DEFERRED / CONDITION-BASED, not an operational Phase 11 blocker.** Leave current production OAuth credentials unchanged. Do not force expiry, manually rotate, or trigger refresh solely for testing. When the token naturally enters its configured refresh window and normal server-side refresh occurs, verify successful read-only Pinterest account lookup and updated non-secret expiry/`updated_at` metadata in Neon. Never reveal token plaintext or secrets. Reopen only this verification item when naturally due.
- No real Pin/board creation, publication, production credential rotation, production database mutation, or deployment was performed for this closeout.


## Authoritative Agent Model 1 reconciliation checkpoint — 2026-11-05

This checkpoint supersedes earlier Agent PR/branch status entries above where they conflict. The replacement branch is pushed and PR #62 is open; it has not been merged or deployed.

### Current Agent mainline reconciliation

- Current Agent `origin/main` base inspected: `955c583498a43e2c9a0c8baec584128defd83e3e` (`Add draft-first affiliate product scheduler`). The scheduler code and router are preserved in the reconciliation branch.
- New local branch: `fix/pb06-mainline-reconcile`.
- Reconciliation code commit: `4927a9d9b1624022099245303422cbd45e904315` (`Reconcile Model 1 publishing gateway with current main`). The context checkpoint was committed separately afterward.
- Replacement PR #62: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/62, branch `fix/pb06-mainline-reconcile`, base `main`. PR is **OPEN, READY, and mergeable**. GitHub reports no merge conflict.
- PR #62 exact-head checks on `629eda3a10e094b62bc00ba4989e46722492a304` passed: Python tests run `42056670696` (run #579) and Python CI run `42056670730` (run #699). A subsequent context-only commit is being added; its exact-head CI must also pass before merge.
- Earlier Agent PR #61 (`fix/pb06-analytics-forward-port`) remains open and dirty/unmergeable. It has not been merged or force-pushed. Do not merge PR #61; close it as superseded only after PR #62 is merged.

### Reconciled implementation

- Manual Hub publishing and generated workflow publishing delegate to the single `app/publishing_gateway.py` boundary. The only application Pinterest HTTP `POST /pins` call is in that file. The generic workflow Pinterest helper rejects direct `POST /pins`; legacy `/publish` and `/products/{product_id}/content/{content_version_id}/publish` routes return HTTP 410.
- The gateway validates title/description/alt-text limits and required inputs before ledger reservation or network I/O; blocks pending/unknown/succeeded duplicates; blocks reuse of a publication row owned by a different or unknown Pinterest account; and records uncertain provider outcomes without blind retry.
- Manual drafts persist their supplied image URL, content version, idempotency key, and request fingerprint. A reused key with a different payload is rejected. Workflow generation reservations retain fingerprints, leases, and reusable image/content checkpoints.
- Cloudflare image generation uses bounded streaming and configured size limits. The workflow resolves an existing board using read-only paginated GET requests and does not create a board.
- Protected read-only publication verification was restored: it reads all board pages and the stored Pin detail, returns non-secret verification fields, and performs no Pinterest writes. Operator reconciliation remains a separate authenticated transition.
- Organic analytics and read-only Trends/Featured Topics remain active. Advertiser-account and audience-insights routes were removed from the active Agent surface; `ads:read` and audience insights are deferred to Model 2. Do not request that scope, reconnect the account, or trigger new consent for Model 1.
- OAuth refresh metadata preservation was restored: if Pinterest omits a new refresh-token expiry, the existing valid stored expiry is retained. The refresh tests use mocked Pinterest responses; no live refresh or credential rotation occurred.
- The existing affiliate product scheduler and router from current `main` remain included. README endpoint/Model 2 documentation was reconciled with the active code.

### Verification on the reconciliation branch

- Full local suite: **162 passed, 18 skipped**, one existing Starlette/httpx TestClient deprecation warning.
- Isolated Neon integration branch (`agent-integration-tests-20261105`, branch ID `br-damp-unit-arycxn7x`): **25 passed**, one existing deprecation warning. This run used only the isolated test database and mocked Pinterest/provider traffic; it did not mutate production data.
- `python -m compileall -q app tests`: passed.
- `git diff --check`: passed.
- Bandit (`-ll`): passed with no medium/high findings.
- `pip-audit --local`: no known vulnerabilities.
- The PB-10 backend-termination integration test remains skipped because `PB10_TEST_DATABASE_URL` is not configured. The PostgreSQL publication-recovery and token-refresh integration tests were separately run against the isolated Neon test branch and passed.

### Production and safety boundary

- Production Neon migrations 011/012 were applied and read-only verified earlier on production branch `br-shy-sea-arz8zzkh`: `products.request_fingerprint`, `workflow_generation_reservations`, its expiry index, and both `schema_migrations` ledger entries are present. No additional production schema/data mutation occurred in this reconciliation.
- Modern Living Hub PR #21 remains merged/deployed as recorded above. No new Hub change or deployment was made here.
- The new Agent branch was pushed and PR #62 opened; no Agent merge or Render deployment has occurred. No live Pinterest request, Pin creation, Board creation, OAuth refresh/reconnect, token rotation, or production database write occurred. All provider-facing tests used mocks; PostgreSQL integration used only the isolated Neon test branch.

### Next execution order

1. Let the context-only PR #62 head update finish exact-head GitHub CI; verify required `test` and `pytest` checks are green.
2. Merge PR #62 only when exact-head checks are green and GitHub permits the protected merge. Then close PR #61 as superseded.
3. Verify the exact Agent Render deployment commit and read-only health/readiness/diagnostic endpoints after merge.
4. Do not use a live Pin or Board creation as a test. Do not trigger OAuth refresh; PB-05 remains condition-based until natural refresh is due.


## Model 2 architecture-first directive — 2026-11-08 (owner instruction; current)

- Owner explicitly directed: **freeze the complete Model 2 architecture first, lock it, and only then implement in that exact order.** Do not continue coding features before architecture approval/freeze.
- Owner's permanent implementation rule reaffirmed: **never recreate functionality that is already implemented.** Inspect and verify existing code, schemas, routes and tests first; reuse completed Model 1 capabilities; implement only demonstrated gaps. Do not repeat work or create duplicate systems.
- The detailed architecture baseline is `docs/MODEL2-FOUNDATION.md`. It defines Model 2 objectives, existing Model 1 reuse boundaries, target components/data flow, schema/security rules, explicit exclusions, sequential implementation gates 0–10, and evidence requirements.
- Current status of architecture document: **FROZEN / LOCKED** per the owner's direct instruction to create and lock the architecture before implementation. Any architecture change requires an explicit owner-approved revision.
- Existing artifacts in the isolated Model 2 worktree remain draft only:
  - `migrations/013_model2_account_niche_registry.sql`
  - `tests/test_model2_registry_migration.py`
  - `tests/test_model2_registry_postgres.py`
  - `docs/MODEL2-FOUNDATION.md`
  These were created before the architecture-first instruction. They must be reviewed against the approved architecture; retain, revise or remove only after review. Do not apply migration 013 to production.
- Verified current branch/worktree: `feat/model2-open-source-reuse` at the production-main-derived baseline `785efd99849627062c1fff8504d21ca91abfee8e`; four Model 2 draft files are untracked. No commit/push/PR/merge/deploy has occurred in this checkpoint.
- Runtime tests remain **NOT RUN** in this isolated worktree because pytest/runtime dependencies and PostgreSQL client were unavailable. Earlier static checks passed only; do not report integration tests as passing.
- Hard boundaries remain: do not touch the owner backup worktree or clean production snapshot; no production DB migration/write, Render deploy, OAuth refresh/rotation, live scheduler run, real Pinterest Pin/Board creation, image hosting, Personal Browser/UCOS Browser integration, or Modern Living Hub coupling.
- Next permitted work: Phase 1 existing-capability inventory only, following the frozen sequence. Before every implementation item, inspect current code/schema/routes/tests and prove the capability is missing; skip anything already implemented and verified, recording its evidence instead of rebuilding it. Any proposed architecture change requires explicit owner approval.


## Mandatory open-source reuse rule — 2026-11-08 (owner hard rule)

- Owner added a permanent hard rule: **when a suitable open-source solution exists and has been verified, use/reuse it. Do not build the same capability from scratch. Implement only the functionality that cannot be satisfied by a verified suitable open-source option or by existing project code.**
- Apply this rule before every Model 2 implementation phase:
  1. Inspect the current repository and its existing dependencies/components first.
  2. Search for a suitable open-source project/library only where a genuine gap remains.
  3. Verify the candidate's actual repository, current maintenance/activity, release/API compatibility, security posture where evidence is available, dependency/supply-chain implications, and exact license/obligations.
  4. Prefer existing project code or a compatible, maintained open-source dependency over custom implementation when it meets the requirements.
  5. If no suitable verified option exists, document the search/evaluation and why candidates fail; then implement only the smallest missing component.
  6. Add tests and integration adapters around the selected solution; do not fork/rewrite its core functionality unnecessarily.
- "Open source" alone is not sufficient verification. Do not import code or add a dependency until license compatibility and obligations are reviewed. AGPL-3.0 projects (including Postiz/Postmill references previously reviewed) remain **not approved for code import** unless the owner separately authorizes after license review. Their architecture may be used as reference only.
- Do not invent a library's capabilities, maintenance status, license, security properties or compatibility. Record sources/versions and evidence; if a candidate cannot be verified, treat it as unverified and do not rely on it.
- This rule applies alongside the existing no-duplication rule: reuse verified Model 1 functionality first, then verified compatible open-source solutions, and custom-build only the residual gap.
- Update the frozen architecture's engineering rules and sequential phase gates to require an open-source reuse assessment before custom implementation. This is an owner-directed clarification to the frozen baseline; record it as an approved architecture revision/addendum rather than silently changing scope.


## Model 2 Phase 1 — existing capability inventory checkpoint (2026-11-08)

- **Phase 1 source inventory completed** in `docs/MODEL2-PHASE1-INVENTORY.md`. Scope covered current FastAPI routes/auth dependencies, Pydantic models/validation, database helpers/migrations, credential vault, publishing gateway/ledger, workflow, scheduler, Learning Loop/raw analytics, dashboard, dependencies and related tests.
- Current source baseline is commit `785efd99849627062c1fff8504d21ca91abfee8e` in isolated worktree `/root/restore-staging/Pinterest-Agent-model2-worktree`, branch `feat/model2-open-source-reuse`.
- Existing capabilities confirmed for reuse: FastAPI routing, Pydantic validation, Psycopg 3 pool/migration abstraction, encrypted OAuth credential vault, canonical publishing gateway and publication ledger, product/content persistence, workflow reservations/checkpoints, draft-first scheduler, raw Pin analytics/Learning Loop, read-only dashboard/diagnostics, and direct Base64 media flow.
- Genuine Model 2 gaps identified: account profile/ownership authorization; metadata-only connected-credential lookup (current vault getters decrypt and return token material internally); niche taxonomy and account–niche repository/API; explicit niche attribution to content/publications; account+niche learning projection; multi-niche schedule policy; account/niche dashboard isolation; and a true per-user/tenant auth model. Shared API key is service authentication, not proof of human ownership.
- Existing scheduler has one-active-schedule-per-account uniqueness and no niche dimension. Do not implement multi-niche scheduling until Phase 9 design proves board/account quotas, idempotency and recovery.
- Open-source assessment: current stack already has suitable verified components (FastAPI MIT, Pydantic MIT, Psycopg 3 LGPL-3.0-only, cryptography Apache-2.0 OR BSD-3-Clause; Python stdlib `zoneinfo`). Reuse these; no new package is currently justified. Official license/source references are recorded in the Phase 1 inventory. Exact resolved dependency tree/SBOM not verified because requirements are ranges and no lockfile was found.
- Draft migration 013 and its two tests already existed as untracked artifacts before this phase. They are proposals only and require Phase 2 schema review; no Model 2 API/repository implementation exists yet.
- Test execution: `python3 -m pytest --version` failed with `No module named pytest`; full pytest and PostgreSQL integration tests remain **NOT RUN**. `git diff --check` passed. No production verification was performed.
- No production DB changes, Render deployment, GitHub commit/push/PR/merge, OAuth operation, Pinterest write, Pin/Board creation, image hosting, or changes to owner backup/clean snapshot occurred.
- **Next sequence:** Phase 2 schema review only. Review migration 013 against frozen constraints, identify necessary corrections, inspect migration runner/rollback and attribution constraints, and evaluate whether the four proposed tables are sufficient. Do not apply it to production.


## Model 2 Phase 2 — schema review checkpoint (2026-11-08)

- Draft migration `013_model2_account_niche_registry.sql` reviewed against frozen architecture and existing migrations. Detailed findings saved in `docs/MODEL2-PHASE2-SCHEMA-REVIEW.md`.
- **Phase 2 remains IN PROGRESS / NOT CLOSED.** Owner decision A was received and the isolated migration/test draft was revised; runtime verification and remaining exit gates are pending.
- Remaining implementation constraints:
  1. Owner selected a single-operator deployment model; shared API key remains service authentication, not a distinct human identity.
  2. Account profile is not FK-linked to the existing `pinterest_credentials.account_id`; canonical `pinterest:` ID validation is not enforced.
  3. Revised draft adds immutable publication-to-niche attribution with composite account and niche foreign keys; gateway transaction integration remains future work.
  4. Revised draft bounds JSONB settings and restricts metrics to existing Learning Loop metric keys and nonnegative numeric/null values.
  5. Profile timezone only has a length check; reuse existing Python `ZoneInfo` validator.
  6. Revised draft uses pause/archive states and restrictive foreign keys; credential status remains authoritative in the existing vault.
  7. Existing Agent trends validators already support US and GB+IE; revised draft reuses that taxonomy.
  8. Existing scheduler has one active schedule per account and no niche dimension; multi-niche scheduling remains Phase 9 design only.
- Four static test functions for the revised migration were manually invoked and passed. PostgreSQL test source now covers credential/profile linkage, membership, primary-niche uniqueness, account separation, immutable publication attribution, raw analytics lineage capture, deferred source-count checks and cross-account rejection; real PostgreSQL execution remains pending.
- Open-source decision: reuse current FastAPI/Pydantic/Psycopg 3/cryptography stack and Python stdlib `zoneinfo`; no new package or ORM is justified. License/source evidence is recorded in `docs/MODEL2-PHASE1-INVENTORY.md`. No external dependency added.
- Environment: no `psql`, `pg_isready`, `postgres`, or `pytest` executable; system Python 3.11.2 has no pytest. No DB connection or runtime integration test was attempted.
- No application source code was changed during Phase 2 review; the isolated migration and test drafts were revised after owner decision A. No production DB, Render, GitHub write, OAuth, Pinterest API write, Pin or Board was touched.
- Owner decision A received: one operator manages multiple Pinterest accounts. No multi-tenant users or synthetic owner identity is introduced.
- Revised migration 013 and both focused test files remain draft-only. Next: validate migration SQL and static tests, then run PostgreSQL integration only against a verified disposable database. Do not advance to Phase 3 until Phase 2 exit gates pass.

## Model 2 Phase 2 — owner model decision and revised schema draft (2026-11-08)

- Owner selected **A: one owner/operator manages multiple Pinterest accounts**. Model 2 is deployment-scoped to one operator; no multi-tenant users/tenants or synthetic owner IDs will be introduced. Each Pinterest account remains separately scoped by the existing canonical pinterest:<user_id> account ID.
- Existing shared API key is service authentication only, not proof of a distinct human identity. Do not invent created_by_user_id or claim multi-user isolation. Registry write routes remain behind the existing protected operator/service boundary.
- Revised only the isolated draft migration 013 and its two tests; updated docs/MODEL2-PHASE2-SCHEMA-REVIEW.md.
- Revised schema includes: profile FK to existing pinterest_credentials(account_id) with canonical pinterest: prefix validation; active|paused operator profile state (credential status remains authoritative in existing vault); restrictive FKs/no cascaded historical deletion; explicit immutable model2_publication_niche_attributions keyed to exact publication/account/niche mapping; bounded JSONB settings (empty until defined) and metrics (existing four Learning Loop metric keys only); sample_size <= source_snapshot_count; existing US / GB+IE market taxonomy reused.
- Attribution must be written inside the existing publishing gateway's PostgreSQL reservation transaction before provider network I/O in a later approved implementation phase. Existing raw analytics remain in pin_analytics_snapshots and join through publication_id. No legacy NULL-account publication may be guessed or backfilled.
- Metadata-only credential existence lookup, gateway attribution integration, timezone validation via existing ZoneInfo, repository/API work, and PostgreSQL integration tests remain future phase work. No app source was modified.
- git diff --check passed after the edits. Pytest and PostgreSQL migration/integration tests have not been run in this checkpoint. No PostgreSQL connection, production DB mutation, commit/push/PR/merge/deploy, OAuth operation, Pinterest API write, Pin/Board creation, image hosting, or changes to owner backup/clean production snapshot occurred.

- This 2026-11-08 owner-decision checkpoint supersedes the earlier Phase 2 review bullets that said the ownership model was undecided and that attribution did not exist in the draft. Phase 2 is still not closed; schema/runtime verification remains pending.

- Deeper lineage review added a sixth draft table, model2_learning_snapshot_sources. It links each aggregate to exact pin_analytics_snapshots.id, publication, account and niche via composite restrictive FKs. Deferred constraint triggers validate source_snapshot_count equals source rows and sample_size equals distinct attributed publications at transaction commit. Source lineage is immutable. Static test coverage expanded to this lineage contract. This is still an unapplied draft; PostgreSQL execution is pending.

- Further lineage hardening: Model 1's Learning Loop uses ON CONFLICT DO UPDATE for an existing Pinterest Pin/date-range analytics row. The Model 2 source-lineage table now captures the exact JSONB metrics via a BEFORE INSERT trigger, so later Model 1 refreshes cannot rewrite the historical input used by a Model 2 aggregate. PostgreSQL test source now exercises source capture, immutability, deferred count mismatch and cross-account rejection. Test fixture teardown truncates only immutable lineage tables inside the explicitly disposable TEST_DATABASE_URL database and cleans its uniquely named synthetic rows. None of these PostgreSQL tests have been executed locally.

- PostgreSQL test-source review caught and corrected the count-trigger preconditions: membership-only aggregates now declare zero source rows, while the cross-account rejection case also uses zero counts so its expected FK failure is not masked by a deferred count error. The positive lineage test now refreshes a raw analytics row after aggregation and asserts the immutable captured metrics remain unchanged.

- Phase 2 gate clarified: metadata-only credential lookup and gateway attribution integration are future Phase 4/6 implementation requirements, not prerequisites to schema-review closure. Phase 2 itself remains open until migration 013 executes successfully on a verified disposable PostgreSQL 16 database, focused static + PostgreSQL tests pass, test cleanup is verified, a forward-fix recovery plan is documented, and owner accepts the final schema contract. No TEST_DATABASE_URL is configured on the current device, and no pytest/PostgreSQL server binaries are available; no DB was contacted.

### Model 2 Phase 2 — additional source-only audit findings (2026-11-08)

- Re-ran the four static migration test functions directly: **4/4 passed**. Python compilation of both Model 2 test files passed; `git diff --check` passed. These are static/source checks only, not pytest collection or PostgreSQL execution.
- Additional concurrency review identified an unresolved race in `model2_validate_learning_snapshot_source_counts`: two transactions may concurrently add different source rows to an already-committed learning snapshot. Without serialization on the parent snapshot row, each deferred trigger may count only its own uncommitted row and both transactions could commit, violating the final source count. Required before approval: parent-row serialization with a documented lock order and a real two-connection PostgreSQL regression test. Migration 013 was not changed pending executable verification.
- The PostgreSQL fixture truncates both immutable lineage tables during cleanup. This is safe only on a dedicated disposable test database with serialized tests; parallel fixtures could erase each other's rows. Before any run, independently verify TEST_DATABASE_URL is disposable and distinct from DATABASE_URL, and run the test file without parallel workers. A parallel-safe cleanup design remains future work if parallel execution is required.
- Current environment still has no pytest, psql, postgres, initdb, psycopg, psycopg_pool, or SQL parser package; TEST_DATABASE_URL is unset. The `docker` executable is a previously identified udocker wrapper, not verified Docker Engine. No database was contacted and no migration was applied.
- Phase 2 remains IN PROGRESS. Active isolated worktree only; no application source edits, commit, push, PR, deployment, production DB operation, OAuth action, Pinterest write, Pin/Board creation, or Personal Browser activity.


### Model 2 Phase 2 — concurrency serialization draft update (2026-11-08)

- Addressed the source-only concurrency finding in migration 013 draft: added `model2_lock_learning_snapshot_source_parent()` and a `BEFORE INSERT` trigger that obtains `SELECT ... FOR UPDATE` on the parent learning snapshot before accepting a source row. Writers targeting the same snapshot serialize; callers inserting across multiple snapshots should use ascending learning_snapshot_id lock order. This is a draft-level design fix, not a runtime-verified guarantee.
- Added static regression `test_model2_learning_source_writers_serialize_on_parent_snapshot` and two-connection PostgreSQL regression `test_model2_learning_source_concurrent_inserts_are_serialized`. The runtime test holds writer one open, starts writer two, asserts it blocks, then expects writer two to fail deferred source-count validation after writer one commits.
- Latest checks: **5/5 static migration test functions manually passed**; `py_compile` passed for both Model 2 test files; `git diff --check` passed. These are source/static checks only.
- PostgreSQL runtime tests remain NOT RUN. Current environment: `TEST_DATABASE_URL` unset, `DATABASE_URL` unset, pytest/psycopg/psycopg_pool/psql/postgres/initdb unavailable. No DB was contacted. No migration applied.
- Fixture still uses database-wide TRUNCATE for immutable lineage tables; only run the PostgreSQL file serially on a verified disposable TEST_DATABASE_URL. Parallel-safe fixture cleanup is not implemented.
- Phase 2 remains IN PROGRESS. Do not advance to Phase 3, production migration, commit/push/PR/merge/deploy, OAuth or Pinterest writes until all Phase 2 gates and owner schema acceptance are complete.


### Model 2 Phase 2 — approved test environment provisioning and verification (2026-11-08)

- Owner approved a test-only local PostgreSQL environment. Device inspection: Debian 12 ARM64, root shell with no Linux capabilities, approx. 8.4 GB free disk initially.
- Installed official PostgreSQL server/client **16.15** from PGDG APT repository; signing key fingerprint verified as `B97B 0AFC AA1A 47F0 44F2 44A0 7FCC 7D46 ACCC 4CF8` (full fingerprint in Phase 2 review). Installed no project dependencies or changed requirements/lockfiles.
- Created external venv `/root/.venvs/model2-pg16` with pytest 9.2.0, Psycopg 3.3.8, psycopg-pool 3.3.3, Pydantic Settings 2.16.2 and pglast 8.7.
- Local PostgreSQL cluster creation is not possible in this Android-hosted kernel: initdb repeatedly fails with `could not create shared memory segment: Function not implemented` on `shmget`; kernel SysV shared-memory sysctls are absent and `unshare -Ur` fails with `Invalid argument`. Mmap/huge-pages settings did not resolve it. The package post-install default cluster also failed; `pg_lsclusters` reports no cluster. No PostgreSQL server started and no migration was executed.
- `DATABASE_URL` and `TEST_DATABASE_URL` were both unset. Tests were run from `/tmp` with secret-bearing environment variables explicitly unset; no repository `.env` file was loaded. No production DB or external provider was contacted.
- Updated migration 013 concurrency protection: added `source_lock_version BIGINT NOT NULL DEFAULT 0 CHECK (source_lock_version >= 0)` to `model2_learning_snapshots`; the BEFORE INSERT source trigger increments this field via a real parent UPDATE. This serializes READ COMMITTED writers and causes stale REPEATABLE READ/SERIALIZABLE writers to receive serialization failure rather than commit using an old snapshot. Lock ordering for multi-snapshot source writes remains ascending learning_snapshot_id.
- Expanded two-connection regression test to cover READ COMMITTED (deferred count rejection) and REPEATABLE READ (SerializationFailure). It establishes the second transaction's snapshot before the first commits and observes actual lock wait using `pg_blocking_pids()`. Test is authored but not executed due unavailable local server.
- Latest actual `pytest -q` on both Model 2 test files: **5 passed, 9 skipped**; all 5 static tests passed, all 9 PostgreSQL integration cases skipped because TEST_DATABASE_URL is unset. This is not an integration-test pass.
- Both test files `py_compile`: PASS. `pglast 8.7` parsed all **14/14 numbered migration SQL files** and all **5/5 PL/pgSQL functions** in migration 013. `git diff --check`: PASS. Parser success is not live PostgreSQL execution.
- Phase 2 remains IN PROGRESS / NOT CLOSED. Need a Linux host or CI runner with functional PostgreSQL 16 shared memory/IPC and normal filesystem ownership to run full migration sequence and integration tests against a verified disposable DB. Keep tests serial because fixture teardown globally truncates immutable lineage tables.
- No commit, push, PR, merge, deploy, production DB action, OAuth operation, Pinterest API write, real Pin/Board creation, or Personal Browser activity occurred. Owner backup worktree and clean production snapshot remain untouched.

- Owner approved a dedicated PostgreSQL 16 GitHub Actions test workflow and push limited to the Model 2 feature branch. Added `.github/workflows/model2-postgres-integration.yml`: push trigger only for `feat/model2-open-source-reuse`, PR target `main`, manual dispatch; ephemeral loopback-only `postgres:16` service/database `model2_test`; `DATABASE_URL` forced empty; TEST_DATABASE_URL target asserted before running the two Model 2 test files. The test fixture invokes `database.run_migrations()` and applies all numbered migrations to that ephemeral DB. No secrets or production service configuration are passed. No PR creation, merge, deployment or production DB operation approved.
- Local workflow validation: no YAML parser installed yet. Python compile and `git diff --check` pass; local pytest remains 5 passed / 9 skipped because PostgreSQL server cannot start on the Android kernel. GitHub Actions run will be the first actual database execution.
- CI preparation review found the new concurrency test used suffixed product/pin/board identifiers that exact-match fixture teardown would miss. Updated teardown to prefix-match the test-specific UUID suffix across analytics, publications, products and content versions; added a static regression assertion. Latest local result: **6 static tests passed, 9 PostgreSQL integration tests skipped**; workflow YAML parsed with PyYAML; `git diff --check` passed. The PostgreSQL cases still await GitHub-hosted PostgreSQL 16 execution.

### First GitHub-hosted PostgreSQL 16 run — 2026-11-08

- Workflow commit `2d418fcee3ea12f99b6268b21fddebff5e189536` pushed successfully to only `feat/model2-open-source-reuse`. GitHub Actions run `42497549120` started a healthy PostgreSQL 16 service, passed the loopback-only disposable DB preflight, installed requirements, and executed the Model 2 test files.
- First real PostgreSQL result: **12 passed, 3 failed**. One expected FK-negative test was masked by primary-niche uniqueness because it attempted a second primary mapping; changed it to `is_primary=FALSE` so it tests the FK independently. Two concurrency cases created a snapshot with expected counts 1/1 and committed before source insertion; deferred count trigger correctly rejected this invalid setup. Corrected test now creates 0/0 snapshot, inserts first source and updates counts to 1/1 in the same first-writer transaction, then lets second writer race under READ COMMITTED or REPEATABLE READ.
- The 12 other PostgreSQL tests passed on actual PostgreSQL 16. This is not a green run; corrected tests still require a new GitHub Actions execution.
- Local after-fix checks: 6 static tests passed, 9 PostgreSQL tests skipped (no local server), YAML parse passed, Python compile passed, `git diff --check` passed.
- Next: push corrected PostgreSQL test and update docs/context only on the same Model 2 feature branch, then inspect the next CI run. Phase 2 remains IN PROGRESS / NOT CLOSED.

- Second GitHub PostgreSQL run `42497741517` on commit `ac731fc6efd540ab9b3373e8bcb73306bbd081f4` returned **12 passed, 3 failed**. Further test-code defects found: the membership test wrongly expected that a second non-primary niche mapping was forbidden (contradicts multi-niche design), and direct Psycopg connections use tuple rows by default, so dict-key indexing prevented the concurrency worker from signaling readiness. Corrected the membership test to prove an explicitly assigned second niche can have a snapshot, while separate test covers one-primary uniqueness; corrected PID/blocker reads to tuple indexing. No migration SQL changed. Latest local: 6 static pass, 9 PostgreSQL skipped; Python compile and diff check pass. Third GitHub run required; Phase 2 remains open.

- Third GitHub PostgreSQL run `42497944796` on commit `eceecc2be3bbc6d93700eb590d27de332a5c2d04` completed successfully: **15 passed, 0 failed, 0 skipped** against disposable PostgreSQL 16.15. This includes 6 static tests + 9 PostgreSQL integration cases, including concurrent source insert regression under READ COMMITTED and REPEATABLE READ. Migration runner executed from the test fixture against a fresh ephemeral DB.
- Added a final workflow post-test gate to compare the complete schema_migrations ledger with all numbered migration files and assert test fixture cleanup left no synthetic credentials/profiles/niches/mappings/learning/source/attribution/analytics/publication/product/content rows. YAML and embedded Python parse/compile locally. This additional gate has not yet run on GitHub.
- Phase 2 remains IN PROGRESS until the new ledger/cleanup gate passes, forward-fix recovery plan is documented, and owner accepts the final schema contract. No non-disposable database received migration 013.
- Documented Phase 2 forward-fix/recovery plan in `docs/MODEL2-PHASE2-SCHEMA-REVIEW.md`: migration runner applies migrations in one pooled-connection transaction and records version after SQL success; SQL failure rolls back uncommitted DDL/ledger changes; no destructive down migration; use fresh ephemeral CI DB, and for any future persistent DB require verified backup/restore rehearsal, isolated clone rehearsal, exact target/approval record, and reviewed forward-fix migration. Restore only if post-backup writes can safely be discarded. No persistent or production DB apply is authorized.

- Final isolated CI gate run `42498159463` on commit `7c83183ba30fad5d4a85687237b6d58c1f46257b` passed on GitHub-hosted PostgreSQL 16.15: **15 passed, 0 failed, 0 skipped** (6 static + 9 PostgreSQL integration tests). Both READ COMMITTED and REPEATABLE READ concurrency regressions passed.
- Post-test gate verified all **14/14 numbered migration files** are recorded in schema_migrations and zero synthetic test leftovers remain across credentials, profiles, niches, mappings, learning snapshots, sources, attributions, analytics, publications, products and content versions. Database target was loopback-only ephemeral `model2_test`; DATABASE_URL empty; service destroyed at job end.
- Phase 2 technical gates satisfied, including full migration execution, focused tests, concurrency, cleanup and forward-fix recovery plan. Phase 2 remains awaiting explicit owner acceptance of final schema contract before Phase 3. No persistent DB/production migration authorized.

### Model 2 Phase 2 — final schema accepted; Phase 2 closed (2026-11-09)

- Owner explicitly approved the final Model 2 Phase 2 schema contract on 2026-11-09.
- **Phase 2 is CLOSED / ACCEPTED.** The reviewed six-table additive registry, account–niche mapping rules, immutable publication attribution, exact raw analytics lineage capture, metric constraints, concurrency protection and deferred count invariants are accepted.
- Technical evidence remains GitHub Actions run `42498273839` on commit `82d18765bc92451d8411b81406ef420f1836712b`: PostgreSQL 16.15, **15 passed / 0 failed / 0 skipped**, all 14 numbered migrations recorded, and zero synthetic fixture rows left after cleanup. Workflow: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42498273839
- Acceptance closes the schema-design phase only. It does **not** authorize applying migration 013 to Neon or another persistent/shared DB, production backfill, PR creation, merge, deployment, OAuth/provider actions, or Pinterest writes. No real Pin/Board was created.
- Next phase under the frozen architecture: **Phase 3 — Domain Contracts**. Follow `docs/MODEL2-FOUNDATION.md`; specify entities, invariants, state transitions and typed boundaries before implementation. Continue reusing Model 1 publisher, credential vault, publication ledger, scheduler, raw analytics and Learning Loop; do not duplicate them.
- Active Model 2 worktree remains `/root/restore-staging/Pinterest-Agent-model2-worktree`, branch `feat/model2-open-source-reuse`. Owner backup worktree and clean production snapshot remain untouched. No commit, push, PR, merge or deployment was performed to record this approval.

### Model 2 Phase 3 — Domain Contracts started (2026-11-09)

- Phase 2 was formally closed after explicit owner schema acceptance; see `docs/MODEL2-PHASE2-SCHEMA-REVIEW.md` section 18.
- Started Phase 3 in accordance with the frozen phase order. New artifacts: `app/model2_domain.py`, `tests/test_model2_domain.py`, and `docs/MODEL2-PHASE3-DOMAIN-CONTRACTS.md`.
- Reuse assessment: existing Pydantic v2 is sufficient for typed contracts; existing stdlib `zoneinfo` validation in `app/affiliate_scheduler.py` is reused; existing region taxonomy `US|GB+IE` is reused from `app/trends.py` and `app/trend_visuals.py`. No new dependency/library added.
- Added pure, side-effect-free contracts for canonical Pinterest account IDs, lowercase kebab-case niche slugs, account profile metadata/status/timezone, niche metadata/region/status, and account–niche assignment state/primary/settings rules. They do not perform DB, vault, Pinterest, OAuth or provider calls.
- Initial focused domain suite: **22 passed**. Full local repository suite: **283 passed, 56 skipped, 1 non-blocking warning**. PostgreSQL integration tests skipped because DB environment variables are unset; no DB was contacted. Python compilation and `git diff --check` passed. Full combined Model 2 test run and final Phase 3 contract/security review are still pending; Phase 3 remains IN PROGRESS.
- Primary uniqueness across multiple mappings remains a database/repository transaction invariant (Phase 4), not something a single input model can establish. Account connection and authorization also remain repository checks; the domain model does not claim either.
- No migration, DB connection, credential access, OAuth/provider operation, Pinterest write, real Pin/Board, PR, commit, push, merge or deployment occurred. Active isolated worktree only; owner backup and clean production snapshot remain untouched.

- Contract cross-check caught and corrected one subtle schema mismatch: migration 013's partial unique index counts only `is_primary=TRUE AND status='active'`, so a paused mapping may retain its primary flag. The initial Phase 3 validator was stricter than the approved schema; it was removed and a regression test now preserves the intended paused/reactivation semantics.
- Combined latest local test run after correction: **28 passed, 9 skipped**. The 9 skipped cases are PostgreSQL integration tests because `TEST_DATABASE_URL` was explicitly unset; the 28 passing cases include 22 domain tests and 6 static migration tests. Full local repository suite: **283 passed, 56 skipped, 1 non-blocking warning**. PostgreSQL integration tests skipped because DB environment variables are unset; no DB was contacted. Python compilation and `git diff --check` passed. No DB was contacted.


### Model 2 Phase 3 — Domain Contracts CLOSED (2026-11-09)

- Phase 3 is formally closed; full contract/schema/security review is in `docs/MODEL2-PHASE3-DOMAIN-CONTRACTS.md` section 7.
- Implemented pure Pydantic v2 contracts in `app/model2_domain.py`: canonical account IDs, bounded lowercase niche slugs, account profile metadata/status/timezone, niche metadata/region/status, and account–niche assignment fields/settings.
- Reused existing Pydantic and stdlib `zoneinfo`; reused Model 1 `US|GB+IE` regions. No new project dependency or dependency-manifest change.
- Final full repository suite: **204 passed, 27 skipped, 1 warning** (22.05s). All 27 skips were database integration gates because `DATABASE_URL`, `TEST_DATABASE_URL` and `PB10_TEST_DATABASE_URL` were unset. No database was contacted. The one non-blocking warning is Starlette's existing httpx/TestClient deprecation notice.
- Focused Model 2 tests: **37 passed, 9 skipped** (the PostgreSQL integration tests intentionally skipped locally). Boundary coverage includes strict types, canonical account identity, slug grammar/length, timezone validity, supported region values, paused-primary behavior and closed settings contract.
- Runtime packages required for full tests were installed only in isolated `/root/.venvs/model2-pg16` from existing `requirements.txt`; repository dependency files were not modified.
- Security review: domain contracts contain no secrets or human actor identity; account ID validation does not establish connection or caller authorization. Phase 4 must enforce account existence and authorization in the repository/service boundary using a metadata-only credential query; do not call token-decrypting/refreshing `get_pinterest_credential` for existence checks.
- No production DB, migration, OAuth/provider operation, Pinterest write, real Pin/Board, PR, commit, push, merge or deployment occurred.
- **Next: Phase 4 — Repository Layer.** Its first task is to inspect and document existing transaction/pool patterns and the credential-vault metadata lookup boundary before writing repository code.


### Model 2 Phase 4 — Repository Layer IN PROGRESS (2026-11-09)

- Phase 3 Domain Contracts are formally closed; evidence is in `docs/MODEL2-PHASE3-DOMAIN-CONTRACTS.md` section 7.
- Phase 4 inventory and implementation are documented in `docs/MODEL2-PHASE4-REPOSITORY-LAYER.md`.
- Reused existing Psycopg 3 pool/connection/transaction pattern in `app/database.py`; no second pool or persistence framework.
- Added metadata-only credential helper `pinterest_account_is_connected_in_transaction` in `app/credential_vault.py`. It selects only account_id for connected state with `FOR SHARE`; it does not read ciphertext, decrypt, refresh OAuth, or call Pinterest.
- Added `app/model2_repository.py` for profile create/update/read/list, niche create/update/read/list, account–niche assignment upsert, and account-scoped assignment listing. Writes use one connection/transaction. Account profile row locking serializes assignment and primary-niche updates; archive/pause transitions retain rows and pause active mappings.
- Added `tests/test_model2_repository.py` unit coverage and seven PostgreSQL integration cases in `tests/test_model2_registry_postgres.py` for metadata-only onboarding, revoked credential reactivation refusal, primary swap/account isolation, niche archival, archived-niche assignment rejection, and concurrent primary selection.
- Updated the dedicated GitHub Actions workflow to run domain, repository, migration and PostgreSQL tests, and expanded post-test fixture cleanup checks for the new test niches.
- Local focused Model 2 test run: **51 passed, 16 skipped** (16 PostgreSQL integration cases skipped because TEST_DATABASE_URL is unset).
- Full repository run after implementation: **218 passed, 34 skipped, 1 warning**. Database integration gates intentionally skipped; no DATABASE_URL, TEST_DATABASE_URL or PB10_TEST_DATABASE_URL was set. No DB was contacted.
- The 7 new PostgreSQL repository scenarios still require the dedicated disposable PostgreSQL 16 GitHub Actions run. Phase 4 is NOT closed until that CI evidence and cleanup gate pass.
- No production DB, migration, provider/OAuth action, Pin/Board, commit, push, PR, merge or deployment has occurred for Phase 4 at this checkpoint.


### Model 2 Phase 4 — Repository Layer CLOSED (2026-11-09)

- Phase 4 is formally closed; final evidence and review are in \`docs/MODEL2-PHASE4-REPOSITORY-LAYER.md\` section 8.
- Commit \`20109276ad9ce5f3c6b9844b74aa57c23d37e660\` was pushed only to \`feat/model2-open-source-reuse\`.
- Authoritative GitHub Actions run **42526560689** succeeded: **67 passed, 0 failed, 0 skipped** on disposable PostgreSQL 16.15. Run link: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42526560689
- All 14 numbered migrations were recorded; post-test cleanup verified zero fixture rows across Model 2 registry/learning tables and synthetic Model 1 publication/analytics/product/content tables. The ephemeral PostgreSQL service was stopped.
- Phase 4 reused the existing Psycopg pool/transaction boundary. Credential-state validation is metadata-only (\`SELECT account_id ... status='connected' FOR SHARE\`); no token/ciphertext read, decryption or OAuth refresh. Assignment writes lock the account profile row; CI proved concurrent primary selection leaves exactly one active primary. Profile pause and niche archive pause mappings without deleting history. Listing is scoped by exact account ID.
- Local full repository suite after Phase 4 implementation: **218 passed, 34 skipped, 1 warning**. CI provides the actual PostgreSQL integration coverage.
- No Neon/production DB, migration, OAuth/provider action, Pinterest write, real Pin/Board, PR, merge or deployment occurred.
- **Next: Phase 5 — Protected Registry API.** Reuse existing fail-closed service API-key authentication and router registration; do not invent human actor IDs or multi-tenant ownership. Test auth failure, account scoping, state conflicts, and absence of provider writes.

### Model 2 Phase 5 — Protected Registry API IN PROGRESS (2026-11-09)

- Phase 4 is formally closed; PostgreSQL CI evidence is GitHub Actions run 42526560689 (67 passed, 0 failed, 0 skipped; 14 migrations recorded; zero test fixtures left).
- Phase 5 design and current implementation are documented in docs/MODEL2-PHASE5-PROTECTED-API.md.
- Added shared fail-closed service-key dependency app/auth.py; app.main.require_api_key imports/re-exports it and require_configured_api_key remains a compatibility alias. Existing Model 1 API tests pass after this auth consolidation.
- Added app/model2_registry.py, a protected /model2 router using the Phase 3 domain contracts and Phase 4 repositories only. Endpoints cover account profiles, niches and account–niche assignments; no delete, provider, OAuth or publishing endpoint.
- Response models are explicit allowlists with extra="forbid". Request validation enforces path/body identity equality and explicit lifecycle fields on PUT to prevent accidental reactivation/default resets.
- Added tests/test_model2_registry_api.py for authentication, canonical IDs, path/body mismatch, state/error mapping, response safety, exact account scoping and no publisher invocation.
- Focused API/domain/repository run: 64 passed, 1 warning. Existing Model 1 API regression suite: 40 passed, 1 warning. Full repository suite: 237 passed, 34 skipped, 1 warning. Database tests skipped locally because DB env vars are unset.
- Dedicated GitHub Actions workflow has been expanded to run Model 2 API tests and existing Model 1 API regressions alongside the disposable PostgreSQL tests. CI for the new Phase 5 changes is pending.
- Phase 5 is NOT closed until feature-branch CI passes on the exact API commit and verifies no provider/production side effects.

### Model 2 Phase 5 — Protected Registry API CLOSED (2026-11-09)

- Phase 5 is formally closed; final evidence is in docs/MODEL2-PHASE5-PROTECTED-API.md section 7.
- Commit b16511de0fa15d9ac07f5dc2e201eadb231b6d25 was pushed only to feat/model2-open-source-reuse.
- Authoritative GitHub Actions run 42527370397 succeeded: 127 passed, 0 failed, 1 non-blocking Starlette/httpx deprecation warning. Run: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42527370397
- All 14 numbered migrations recorded; post-test cleanup found zero fixture rows; ephemeral PostgreSQL 16.15 service stopped.
- Shared fail-closed API-key auth is in app/auth.py and reused by app.main. Model 2 routes use only Phase 3 domain contracts and Phase 4 repositories; all routes protected, path/body IDs matched, lifecycle updates explicit, response allowlists forbid unapproved fields. No provider/Pinterest/publishing side effects.
- Local full suite: 238 passed, 34 skipped, 1 warning. CI executed all PostgreSQL tests.
- No Neon/production DB, migration, OAuth/provider action, Pinterest write, real Pin/Board, PR, merge or deployment occurred.
- Next: Phase 6 — Niche Context Integration. Inspect the existing workflow/content-generation path first; add only optional validated niche context, preserving existing Model 1 behavior when no niche context is supplied.


### Model 2 Phase 6 — Niche Context Integration IN PROGRESS (2026-11-09)

- Phase 5 is closed. Phase 6 implementation details are in docs/MODEL2-PHASE6-NICHE-CONTEXT.md.
- Existing Model 1 workflow/content generator and single publishing gateway are reused; no second workflow or publisher.
- Added optional niche_id to the existing workflow. With no niche_id, the original Model 1 request fingerprint, prompt content, prompt version pin-content-v1, generator arguments and gateway arguments are preserved.
- With niche_id, the workflow requires the exact active account profile + assignment + niche, sends bounded structured metadata as untrusted descriptive context to the existing DeepSeek prompt, includes the metadata snapshot in the workflow fingerprint, and records prompt version pin-content-v2-niche-context.
- Existing publication reservation transaction now locks profile, assignment, niche and connected credential metadata, then inserts the existing pin_publications row and immutable Model 2 attribution in the same transaction before Pinterest POST /pins. No token decryption/refresh is added.
- Existing failed attributed publications preserve and revalidate their niche on retry. Explicit niche retry may attribute a failed legacy reservation; succeeded/pending/unknown legacy publications without attribution cannot be backfilled. Mismatched niche retry and inactive assignment/credential are blocked before Pinterest POST.
- Added workflow/gateway/prompt tests, repository tests, and disposable PostgreSQL attribution/retry tests. CI workflow includes these new tests.
- Focused local suite: 40 passed. Full local suite: 256 passed, 43 skipped, 1 warning. All local DB skips are expected because database env vars are unset; no database was contacted locally.
- Phase 6 remains IN PROGRESS until GitHub Actions disposable PostgreSQL integration and cleanup checks pass on the exact feature commit. No real Pin/Board, provider/OAuth action, production DB/migration, PR, merge or deployment.


### Model 2 Phase 6 — Niche Context Integration CLOSED (2026-11-09)

- Phase 6 formally closed. Evidence: docs/MODEL2-PHASE6-NICHE-CONTEXT.md section 8.
- Commit f8700286cd286a4601bc3d5afcf40500584fafef pushed only to feat/model2-open-source-reuse.
- GitHub Actions run 42531360160 succeeded: 162 passed, 0 failed, 0 skipped, 1 non-blocking deprecation warning. Link: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42531360160
- All 14 numbered migrations recorded; fixture cleanup verified zero Model 2 and synthetic Model 1 rows; ephemeral PostgreSQL service removed.
- No-context Model 1 workflow behavior regression-tested. Niche context is optional, exact-account scoped, active-state checked, bounded and treated as untrusted descriptive data. Fingerprint includes niche metadata snapshot and niche prompt version is distinct.
- Existing publishing gateway and ledger reused; immutable attribution is reserved atomically before Pinterest POST. Legacy success/pending/unknown rows without attribution cannot be backfilled; inactive/mismatched cases block.
- Local full suite: 256 passed, 43 skipped, 1 warning. CI executed the disposable PostgreSQL integration suite with no skips.
- No real Pin/Board, Pinterest API write, OAuth refresh, production DB/migration, PR, merge or deployment occurred.
- Next: Phase 7 — Niche Analytics Projection. Reuse Model 1 raw analytics and immutable Model 2 publication attribution, preserve exact source lineage, missing metrics remain unknown (not zero), read-only descriptive aggregates only.


### Model 2 Phase 7 — Niche Analytics Projection IN PROGRESS (2026-11-09)

- Phase 6 is formally closed. Phase 7 design and implementation checkpoint: docs/MODEL2-PHASE7-NICHE-ANALYTICS.md.
- Reuses existing pin_analytics_snapshots, pin_publications, immutable model2_publication_niche_attributions, model2_learning_snapshots and model2_learning_snapshot_sources. No new migration, raw analytics table, dependency, ML framework or provider integration.
- Added app/model2_learning.py with exact account+niche+period projection, four-metric completeness-aware aggregation, immutable source lineage, idempotent same-period behavior, and protected POST/GET endpoints registered in app.main.
- Only confirmed succeeded publications with matching Pinterest Pin ID and exact niche attribution are included. Current paused/archived mapping state does not erase historical evidence.
- Source analytics/publication rows are locked FOR SHARE through transaction; trigger captures exact raw JSONB values. Missing metrics remain NULL, not zero. No eligible raw rows returns insufficient_data without storing an empty snapshot.
- Added unit/API tests and PostgreSQL tests for attribution/account/period isolation, source capture, Model 1 raw refresh immutability, idempotency, pending publication exclusion and historical paused/archived evidence.
- Local focused projection/API tests: 18 passed, 28 PostgreSQL tests skipped. Full local suite: 274 passed, 48 skipped, 1 warning. Local DB variables are unset; no database was contacted.
- CI workflow includes all new projection tests. Phase 7 remains open until exact-head GitHub Actions PostgreSQL integration and fixture cleanup pass.
- No production DB/migration, provider/OAuth action, Pinterest write, Pin/Board, PR, merge or deployment.


### Model 2 Phase 7 — Niche Analytics Projection IN PROGRESS (2026-11-09)

- Phase 6 is formally closed and pushed to feat/model2-open-source-reuse at commit 96a2338. Phase 6 CI evidence: run 42531360160, commit f8700286cd286a4601bc3d5afcf40500584fafef, 162 passed, 0 failed, 0 skipped; all 14 migrations recorded and fixture cleanup verified.
- Phase 7 implementation is documented in docs/MODEL2-PHASE7-NICHE-ANALYTICS.md.
- Added app/model2_learning.py with protected projection/read APIs, exact account+niche+period filtering, successful publication and matching Pinterest Pin ID checks, immutable source lineage, idempotency and descriptive metric aggregation.
- Missing/null metric values remain unknown (not zero); any incomplete source makes that metric aggregate NULL. Unsupported keys, booleans, non-numeric, negative and non-finite values are rejected.
- Raw analytics/publication rows are locked FOR SHARE during source selection; migration 013 source trigger captures exact raw metrics into immutable lineage.
- Local full suite: 274 passed, 48 skipped, 1 non-blocking warning. PostgreSQL tests skipped because local database env vars are unset; no database was contacted.
- GitHub Actions Phase 7 disposable PostgreSQL gate and cleanup verification remain pending. Do not close Phase 7 until exact feature-branch head CI passes. No production DB/migration, provider/OAuth action, real Pin/Board, PR, merge or deployment.


### Model 2 Phase 7 — Niche Analytics Projection CLOSED (2026-11-09)

- Phase 7 formally closed. Evidence: docs/MODEL2-PHASE7-NICHE-ANALYTICS.md section 8.
- Feature branch commit f918c6bfe4cf55113216f9bdc71f2f614397649f. GitHub Actions run 42532367227 succeeded: 186 passed, 0 failed, 0 skipped in selected test step. Link: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42532367227
- All 14 migrations recorded; fixture cleanup verified zero Model 2 and synthetic Model 1 rows; disposable PostgreSQL container stopped.
- Projection includes only successful exact-account/exact-Pin publications with immutable niche attribution and exact period bounds; raw analytics/publication rows locked FOR SHARE; source metrics captured immutably.
- Missing/null metric stays unknown, not zero. Distinct publication count and raw source-row count are separately tracked. Same-period is idempotent; empty period returns insufficient_data; historical paused/archived attribution remains readable.
- Local full suite: 274 passed, 48 skipped, 1 non-blocking warning; local database tests skipped because no DB env vars.
- No production DB/migration, provider/OAuth action, real Pin/Board, PR, merge or deployment.
- Next: Phase 8 — extend existing authenticated read-only dashboard with account profiles, niche assignments and evidence-backed aggregates. No new frontend/auth/pipeline.


### Model 2 Phase 8 — Read-only Dashboard IN PROGRESS (2026-11-09)

- Phase 7 formally closed. CI run 42532367227, commit f918c6bfe4cf55113216f9bdc71f2f614397649f: 186 passed, 0 failed, 0 skipped; all 14 migrations and cleanup verified.
- Phase 8 design/implementation details: docs/MODEL2-PHASE8-READONLY-DASHBOARD.md.
- Reused existing app/dashboard.py, session auth and embedded HTML; added authenticated GET /dashboard/api/model2 and a read-only account/niche/evidence panel. No new frontend or auth system.
- Displays account profile, canonical ID, statuses/timezone, niche/region/primary mapping, successful attributed publication count, snapshot count and latest evidence period/metrics. NULL renders as Unknown. Paused/archived states and profiles without niche assignments remain visible.
- Uses to_regclass compatibility check so a pre-migration database retains existing Model 1 dashboard behavior. SQL is read-only and does not invoke publisher, scheduler, generator, OAuth or token decryption.
- Focused dashboard tests: 7 passed. Full local suite: 279 passed, 49 skipped, 1 non-blocking warning. Local PostgreSQL tests skipped because DB env vars are unset.
- Phase 8 exact-head GitHub Actions disposable PostgreSQL gate pending; do not close before it passes. No production DB/migration, provider/OAuth action, real Pin/Board, PR, merge or deployment.


### Model 2 Phase 8 — Read-only Dashboard CLOSED (2026-11-09)

- Phase 8 formally closed. Evidence: docs/MODEL2-PHASE8-READONLY-DASHBOARD.md section 7.
- Feature branch commit fa8805027578689277103a891cfebffd4c0781a3. GitHub Actions run 42532785414 succeeded: 194 passed, 0 failed, 0 skipped. Link: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42532785414
- All 14 migrations recorded; fixture cleanup verified; disposable PostgreSQL container stopped.
- Existing signed dashboard session reused. Model 2 read-only API/UI displays profiles, mappings, statuses, successful attributed publication counts and persisted learning evidence; no token/affiliate URL/session secret returned.
- Pre-013 compatibility verified through to_regclass check; Model 1 dashboard remains available when Model 2 schema absent. No write/provider/scheduler/generation/OAuth side effects.
- Local full suite: 279 passed, 49 skipped, 1 non-blocking warning.
- No production DB/migration, provider/OAuth action, real Pin/Board, PR, merge or deployment.
- Next: Phase 9 — account-aware scheduling design only. Do not modify/activate live scheduler until design is separately reviewed and approved.


### Model 2 Phase 9 — Account-aware Scheduling CLOSED (2026-11-09)

- Owner explicitly approved the recommended design: one active schedule per Pinterest account, one explicit niche per Model 2 schedule; multiple niche assignments remain allowed, simultaneous active niche schedules are deferred.
- Design and implementation checkpoint: `docs/MODEL2-PHASE9-ACCOUNT-AWARE-SCHEDULING.md`. Frozen architecture remains `docs/MODEL2-FOUNDATION.md`.
- Added `migrations/014_model2_account_aware_scheduling.sql`: nullable `niche_id` preserves legacy Model 1 schedules; composite FK to exact account+niche mapping; canonical Model 2 account ID check; quota indexes; database immutability trigger for activated schedule configuration. No existing schedule/job rows are backfilled or rewritten.
- Extended `CreateScheduleInput` with optional strict positive `niche_id`. Model 2 draft creation and activation require active profile, exact active assignment, active niche, profile timezone match and connected credential metadata. Credential query selects status only; no ciphertext/token access, decryption or OAuth refresh.
- Activation rejects a replacement while any earlier schedule for that account has queued/processing jobs. Pause cancels queued jobs and leaves in-flight jobs visible. Existing one-active-schedule-per-account index remains.
- Worker passes exact schedule `niche_id` through the existing `ProductWorkflowInput`; Model 1 legacy NULL-niche schedule behavior remains. Existing workflow/gateway remains the only publication path.
- Model 2 account-wide quota counts processing/succeeded jobs across all schedules for the same account using actual `locked_at`/`finished_at` timestamps with `run_at` fallback, account profile timezone and DST-aware local-day boundaries. Model 2 worker claims serialize on the account profile row before schedule/job locks. Legacy NULL-niche quota behavior remains per schedule/local date.
- Added PostgreSQL integration tests for account+niche isolation, timezone mismatch, paused assignment, revoked credential metadata, processing-job replacement guard, prior-schedule event-time quota, exact niche pass-through, schedule immutability and concurrent worker quota. Added DST unit tests and scheduler tests to dedicated disposable PostgreSQL CI.
- Local focused run: **17 passed, 38 skipped, 1 non-blocking Starlette/httpx warning**. PostgreSQL integration tests skipped because `TEST_DATABASE_URL` is unset; no database was contacted locally. Full local repository suite: **283 passed, 56 skipped, 1 non-blocking warning**. PostgreSQL integration tests skipped because DB environment variables are unset; no DB was contacted. Python compilation and `git diff --check` passed.
- Superseded by the final closure checkpoint at the end of this section: exact-head PostgreSQL CI passed 212 tests; all 15 migrations and cleanup verified.
- No production/shared DB migration, live scheduler execution, provider/OAuth action, real Pin/Board, PR, merge or deployment. Workflow is mocked in tests; no real Pinterest publishing occurs.


### Model 2 Phase 9 — FINAL CLOSURE (2026-11-09)

- Phase 9 is formally closed for isolated feature-branch implementation and verification. Owner approved one active schedule per Pinterest account, with explicit niche attribution for Model 2 schedules.
- Final code head: `761204b7e5d09cce6eb5f26543602702d5db606a`; follow-up GitHub Actions run `42536328716` succeeded: **212 passed, 0 failed, 1 non-blocking warning** on disposable PostgreSQL 16.15.
- CI recorded all 15 numbered migrations, verified Model 2 and synthetic Model 1 fixtures cleaned, and completed container shutdown. The run included concurrent same-account quota serialization, independent different-account claims, retry idempotency-key preservation and uncertain-outcome quarantine tests.
- Final local full suite: **283 passed, 56 skipped, 1 non-blocking warning**. Local DB tests were skipped because DB environment variables are unset; PostgreSQL evidence is the CI run above.
- No production/shared DB migration, live scheduler execution, provider/OAuth action, real Pin/Board, PR, merge or deployment occurred or is authorized. These require separate approval.


### Model 2 Phase 10 — Release Readiness PRE-RELEASE / BLOCKED (2026-11-09)

- Started Phase 10 after Phase 9 closure. Review document: `docs/MODEL2-PHASE10-RELEASE-READINESS.md`.
- Security review identified a quota safety gap: scheduler `uncertain` outcomes may represent an already-created Pin. Hardening now counts `uncertain` in Model 2 account quota, blocks replacement while any unresolved uncertain job exists, and prevents automatic completion of schedules with uncertain jobs. Legacy Model 1 quota semantics remain unchanged. Regression test added. Exact-head CI pending.
- Uncertain job reconciliation is not implemented in this phase; fail-closed behavior can leave an account blocked. A documented/tested operator reconciliation path is a release blocker. Do not edit production job statuses or assume an uncertain Pin was not created.
- Existing `.github/workflows/affiliate-scheduler-worker.yml` runs hourly and invokes deployed `/affiliate-scheduler/run-due`; it is a real publication side-effect trigger, not a dry-run. It was not run or changed. Model 2 activation and worker execution require separate explicit owner approval.
- Migration 014 was applied only in disposable PostgreSQL CI. Production-like sanitized snapshot migration rehearsal, backup/restore rehearsal and schema rollback are not verified. Proposed safe rollback retains the additive schema; dropping migration 014 is not approved.
- Shared API key remains service authentication, not human identity or multi-tenant isolation. Worker timing is best-effort hourly, at most one job per invocation.
- R1 fail-closed hardening implemented in `app/affiliate_scheduler.py` and migration 014: Model 2 counts `uncertain` as quota-consuming; uncertain jobs block schedule replacement and automatic completion. Added PostgreSQL integration test and static migration-index assertion. Local full suite: **283 passed, 57 skipped, 1 non-blocking warning**; local DB integration skips are due unset DB environment variables.
- Exact-head CI commit `5f818fa5adb5e3c45b1bd8f52d17926ae2ca2d8e`, run `42536949741`: **213 passed, 0 failed, 1 warning** on disposable PostgreSQL 16.15; all 15 migrations recorded, fixture cleanup verified and PostgreSQL container stopped.
- Phase 10 remains PRE-RELEASE / BLOCKED by missing tested uncertain-job reconciliation/runbook and production-like migration/restore rehearsal, plus explicit owner approvals for production migration, deployment and scheduler activation. No production DB migration, live scheduler action, provider/OAuth action, real Pin/Board, PR, merge or deployment occurred or is authorized.


### Model 2 Phase 10 — Scheduler Job Reconciliation IMPLEMENTED / FEATURE-BRANCH VERIFIED (2026-11-09)

- Implemented the uncertain scheduler-job operator reconciliation path on `feat/model2-open-source-reuse`; this closes the reconciliation implementation/runbook blocker for isolated feature-branch readiness.
- Added `migrations/015_affiliate_job_reconciliation_audit.sql`: one audit row per scheduler job, bounded evidence, outcome/Pin-ID consistency checks, append-only UPDATE/DELETE trigger.
- Added read-only `GET /affiliate-scheduler/jobs/{job_id}/reconciliation?account_id=...` and authenticated `POST /affiliate-scheduler/jobs/{job_id}/reconcile` in `app/affiliate_scheduler.py`; database logic is in `app/database.py`.
- Reconciliation is account-checked and transactionally locks Model 2 profile → niche → assignment → schedule → job. It resolves the scheduler's exact idempotency key through product/content/publication lineage, verifies account and immutable niche attribution, rejects ambiguous/mismatched candidates, and atomically writes publication ledger (when present), scheduler job and audit.
- The reconciliation path never calls Pinterest, refreshes OAuth, invokes the workflow, generates content/media, creates a Board or publishes a Pin. Read-only inspection also performs no provider call.
- Success requires exactly one matching publication ledger row and a verified Pin ID. A missing ledger cannot be marked succeeded. Confirmed absence requires explicit `confirm_pin_absent=true`; job and existing publication become terminal failed. The same idempotency key is never requeued.
- Regression coverage: unknown publication success; stale vs recent pending; no-ledger confirmed absence and no-ledger success rejection; multiple candidates; account mismatch; missing/wrong Model 2 niche attribution; legacy Model 1 linkage; repeated reconciliation; append-only audit; transaction rollback on job-update failure.
- Operator instructions: `docs/MODEL2-SCHEDULER-RECONCILIATION-RUNBOOK.md`. Design/implementation evidence: `docs/MODEL2-SCHEDULER-RECONCILIATION-DESIGN.md`. Phase 10 release scorecard updated in `docs/MODEL2-PHASE10-RELEASE-READINESS.md`.
- Latest exact-head commit `7c9b3484b73f43d40da492038569b0c28b12ad43`, GitHub Actions run `42539115679`: **230 passed, 0 failed, 1 non-blocking warning** on disposable PostgreSQL 16.15. Includes authenticated API tests and read-only PostgreSQL inspection coverage. All **16** numbered migrations recorded; Model 2 and synthetic Model 1 fixture cleanup verified; ephemeral PostgreSQL service stopped. Link: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/actions/runs/42539115679
- The earlier intermediate CI failures were corrected (fixture content-version values, JSONB parameter casts, missing test niche attribution, synthetic fixture cleanup predicates). The final exact-head run above passed tests and cleanup.
- Phase 10 remains PRE-RELEASE / BLOCKED: sanitized production-like migration rehearsal and backup/restore/rollback rehearsal for migrations 014 and 015 are not verified; separate owner approval remains required for production migration, deployment and live scheduler activation. No PR, merge, production migration/deployment, scheduler run, real Pinterest Pin or Board creation occurred.


### Phase 10 security follow-up — 2026-11-09

- Reconciliation audit table hardening: added a statement-level TRUNCATE trigger in migration 015 in addition to existing UPDATE/DELETE row trigger. PostgreSQL CI now checks TRUNCATE rejection; fixture teardown deletes only its own account-scoped rows instead of truncating the audit table.
- Security limitation documented: shared X-API-Key authenticates the service request, not an individual human operator. Current audit evidence is caller-supplied text, not non-repudiable identity proof. Never store credentials or sensitive personal data in evidence. DB owner/superuser can bypass/disable triggers; this is not tamper-proof against privileged administrators.
- Pending verification: rerun the exact feature-branch PostgreSQL CI after this change. No production migration/deployment, PR/merge, scheduler activation, or Pinterest Pin/Board action.


### Reconciliation authentication hardening — 2026-11-09

- Removed the scheduler module's duplicate API-key dependency and reused the canonical `app.auth.require_api_key` dependency. This avoids drift between scheduler and general service authentication; the dependency remains fail-closed (503 if no key is configured, 401 for absent/invalid key).
- Added API regression coverage for both reconciliation GET and POST routes when the service key is unconfigured and when an invalid key is supplied. These tests are included in the PostgreSQL integration workflow's explicit test list via `tests/test_affiliate_scheduler.py`.
- Feature-branch CI must pass on the resulting exact HEAD before this hardening is considered verified. No production access, merge, deployment, scheduler activation, Pinterest Pin or Board creation.


### Authentication refactor CI correction — 2026-11-09

- First CI attempt after centralizing scheduler auth failed during pytest collection: six modules hit a `NameError` because six existing route decorators still referenced the old `require_scheduler_key` symbol.
- Root cause was an incomplete symbol replacement, not an authentication logic failure. All six remaining decorator references were replaced with the canonical `app.auth.require_api_key` dependency.
- The failed run was `42540264184` at commit `0f57fb1`; it did not execute the test suite because collection failed. A new exact-head CI run is required before claiming verification.


### Disposable CI audit teardown correction — 2026-11-09

- The next CI run passed Python dependency setup and the disposable PostgreSQL target guard, but failed during PostgreSQL fixture teardown: the append-only trigger correctly rejected test cleanup DELETEs, and retained audit foreign keys then prevented synthetic publication deletion.
- Corrected only the PostgreSQL test fixture teardown: inside a transaction against the workflow-guarded disposable CI database, disable user triggers on the audit table, delete only rows for that fixture's three synthetic account IDs, and re-enable triggers before commit. A failure rolls back the cleanup and trigger state. Production application code and migration protections are unchanged.
- CI run `42540384478` exposed the teardown failure. New exact-head CI run required for verification.


### Latest exact-head verification — 2026-11-09

- CI run `42540493098` completed **successfully** on commit `98e9ce9ccb3ca2c7549caaffe56ddc4e6998f2ca`.
- PostgreSQL 16.15 integration workflow: **235 passed, 0 failed, 1 warning**.
- All 16 numbered migrations were recorded in the disposable PostgreSQL test database.
- CI verified all Model 2 fixtures and synthetic Model 1 fixture rows were cleaned. Disposable PostgreSQL container teardown completed; workflow conclusion was success.
- This run includes the centralized scheduler authentication refactor, GET/POST missing/invalid API-key regression tests, append-only audit UPDATE/DELETE/TRUNCATE protections, and the transaction-scoped disposable-CI fixture teardown.
- Warning observed: Starlette TestClient/httpx deprecation and GitHub Actions Node.js 20 deprecation notices; no test failures. These warnings are maintenance items, not test failures.
- No production database migration, deployment, merge, PR, live scheduler activation, Pinterest Pin, or Board was performed.


### Populated legacy migration rehearsal added — 2026-11-09

- Added `tests/test_model2_legacy_upgrade.py`, which creates a separate database only on the workflow-guarded loopback PostgreSQL 16 CI service, applies all 14 SQL migration files numbered 001–013 (there are two distinct 009 files), inserts a synthetic populated legacy Model 1 schedule/source/queued job, then applies migrations 014 and 015.
- The test asserts the legacy schedule remains `niche_id IS NULL`, its active status, board metadata and queued job/idempotency lineage are preserved, the existing one-active-schedule index remains, and legacy schedule update semantics still work.
- The temporary database is dropped with FORCE in a finally block. The test explicitly refuses DATABASE_URL or any non-loopback/non-CI target.
- Added this test to the Model 2 PostgreSQL CI workflow. CI result is pending; do not call the rehearsal passed until its run is green.
- This synthetic populated upgrade test is not a sanitized production clone and does not replace a production-like restore/rollback rehearsal.


### Populated legacy upgrade rehearsal — CI PASS (2026-11-09)

- GitHub Actions run `42540730785` completed successfully on commit `3ba1ef15d910039aa98f7f876760e209c2d2b44d`.
- Test suite result: **236 passed, 0 failed, 1 warning**.
- New `tests/test_model2_legacy_upgrade.py` passed: on a separately created disposable PostgreSQL 16 database, migrations 001–013 were applied, a synthetic active legacy Model 1 schedule/source/queued job were inserted, then migrations 014–015 were applied. The test verified legacy schedule `niche_id=NULL`, active status, board metadata, queued job/idempotency lineage, retained one-active-schedule index and legacy schedule update semantics.
- Temporary upgrade database was dropped in the test's finally block. The main disposable CI database recorded all 16 migration files and all test fixtures were cleaned. Container teardown completed and workflow conclusion was success.
- This materially improves migration compatibility evidence but remains synthetic. Sanitized production-like snapshot rehearsal, backup/restore and production rollback rehearsal remain open.


### Trusted Hub authentication hardening — 2026-11-09

- Centralized the separate `X-Credential-Ingest-Key` check in `require_credential_ingest_key`; it is intentionally distinct from the general `X-API-Key` because it protects the Modern Living Hub server-to-server boundary.
- The dependency now fails closed with HTTP 503 when the credential-ingest key is not configured, and HTTP 401 when a caller omits or supplies an invalid key.
- Applied the dependency at the FastAPI route boundary for credential ingestion, OAuth refresh, bounded Pinterest account operations, analytics ingestion, and manual publishing. Removed repeated inline checks from the credential, refresh and operation handlers.
- Added regression tests proving missing configuration blocks credential storage, OAuth refresh, and the Pinterest `create_board` operation before any side effect; invalid keys return 401 for all three. These tests use synthetic values and do not call Pinterest, create a real Board, or publish a Pin.
- Also added missing-key fail-closed coverage for diagnostics and analytics learning routes, and centralized the end-to-end workflow route on `app.auth.require_api_key`.
- Exact feature-branch CI run `42542035022` passed on commit `3011674c990df91fc611742199676b31c4c0c0dd`; the PostgreSQL integration job, static/integration tests, migration-ledger verification, fixture cleanup, and container teardown all completed successfully.
- This verifies service-key enforcement in CI only. Shared service keys still do not identify individual humans or provide per-operator authorization/non-repudiation. Secret rotation, log-redaction review, sanitized production-like restore/rollback rehearsal, and owner approval remain release gates.
- No production database was accessed or changed. No PR, merge, deployment, live scheduler activation, real Pinterest Board, or real Pin was performed.
