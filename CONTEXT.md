# CONTEXT — Pinterest Affiliate Marketing Agent

Last updated: 2026-10-27

## Model 1 architecture
Target audience: USA and UK; home decor and kitchen.
Core flow: product idea/details → image generation → title, description and alt text → affiliate URL → Pinterest API publish → analytics ingestion and measured learning loop.
Stack: FastAPI, Render, Neon PostgreSQL, Pinterest API, Cloudflare Workers AI / Cloudflare Images, DeepSeek.

## Verified current status

### Cloudflare Workers AI — REAL IMAGE GENERATION VERIFIED LOCALLY
- On 2026-10-25, the local Termux script called Cloudflare Workers AI model `@cf/black-forest-labs/flux-1-schnell`.
- The API returned **HTTP 200** with `Content-Type: application/json`.
- The script decoded the returned image data successfully and wrote a real image file of **438,335 bytes** (about 429 KB) to `~/cloudflare-test.png`.
- The image was copied successfully to Android Downloads as `~/storage/shared/Download/cloudflare-test.png` and visually confirmed by the user in the file manager. It depicts a kitchen countertop spice rack with spice jars.
- Conclusion: the Cloudflare token/account configuration used in that local test is valid for this Workers AI inference request, and real image generation works. This confirms image generation only; it does **not** yet verify Cloudflare Images upload, a public HTTPS variant URL, or Pinterest publishing.
- The token was entered through hidden terminal input and is **not stored in this context file**. Never paste credentials into chat, commit them, or print them in logs.

### Remaining verification / blockers
- Test Cloudflare Images upload separately and verify the returned public HTTPS variant URL.
- Confirm the production Render service has matching working Cloudflare credentials and the deployed image-generation path works end-to-end; local success does not automatically prove Render's environment is correct.
- Pinterest account access/scopes were verified. One user-approved public Pin is published and verified; do not publish additional Pins without separate explicit approval.
- Never use an affiliate tag that may belong to another person. PB-02: the user confirmed ownership of tracking ID `beautybloo0ff-20` and verified the single approved test Pin; do not publish another Pin without separate approval.
- `/learning-loop/run` analytics ingestion and descriptive evaluation are implemented and tested, including account scoping and rejecting incomplete Pinterest metrics. A real production analytics snapshot is still unverified. Predictive ML is intentionally deferred until enough longitudinal data exists.
- Do not run billable diagnostic calls or upload public test images without explicit user approval.
- Never claim a Pin was published without a real Pinterest Pin ID and database verification.

## Deployment references
- GitHub repository: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
- Render service: https://pinterest-affiliate-marketing-agent.onrender.com
- Keep Modern Living Hub service unchanged unless the user explicitly authorizes changes.

## Next steps
1. Run an explicit Cloudflare Images upload test using the already-generated local PNG; confirm upload response and HTTPS variant URL. This may create a public image and incur usage, so obtain approval first.
2. Verify Render environment and image-generation endpoint without exposing secrets.
3. Do not repeat the already-approved public test Pin without separate user approval.
4. Verify one real production analytics snapshot when Pinterest has suitable metrics; keep predictive ML deferred.


## Historical PB-01 / PB-02 notes — current status supersedes older statements
- PB-02 is closed for the one specifically approved test Pin: `https://www.pinterest.com/pin/1069323505300280780/`. Pinterest “Visit site” was verified to open the intended Amazon product using tracking ID `beautybloo0ff-20`. No further Pin is authorized by that one-off approval.
- PR #15 (`fix/pb01-board-before-persistence-20261026`) has a fix for PB-01 idempotency recovery: board lookup happens before product/content persistence so a board lookup failure does not consume the idempotency key. It adds regression tests for this behavior and for an ambiguous publish response without a Pin ID. PR remains open/unmerged.
- Verified GitHub Actions for PR #15 latest head `c121376e4d8adf58d4a22078352ec1a04e0008dd`: Python tests run #35 and Python CI #120 both passed at 2026-10-26 10:31:49Z. Earlier transient failure on intermediate commit `c1be0ea...` was superseded by passing latest runs.
- Those PR #15 GitHub CI results validate the PR head only; a local integration against the currently deployed `main` was separately conflict-resolved and tested on Debian.
- No new Pin or board was created, no public image was uploaded, and no production configuration was changed during subsequent validation.
- PB-01 is locally integrated with recovery tests but not merged/deployed. Current Render deployment remains `b93edff0ef8fdbc9d21f5b32cc36a89c22e3632f`; PB-03 through PB-07 changes below remain local until the approved GitHub release path is restored.
- PR: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/15


## PB-03 update — 2026-10-27 (fresh production checks)
- Remote Desktop Commander device is ONLINE (Android/Termux, version 0.3.1). Device shell/file access recovered and safe diagnostic scripts were created locally at `pb03_diagnostics_safe.py` and `pb03_config_checks_safe.py`; do not commit these scripts (they use the local environment's APP_API_KEY and print result fields only).
- Fresh authenticated `POST /diagnostics/run` for account `pinterest:1069323642682526567` returned HTTP 200 and `ok: true` for: Neon read-only SELECT, stored Pinterest credential `/user_account` read (HTTP 200), Cloudflare Workers AI real image generation using `@cf/black-forest-labs/flux-1-schnell`, and DeepSeek `deepseek-flash` generation returning title/description/alt text. No Pinterest Pin was created; no product or image was persisted/uploaded by this diagnostics endpoint. AI/provider usage may be billable.
- Fresh `GET /diagnostics/providers`: DeepSeek `/models` verified HTTP 200; Cloudflare Workers AI model-search endpoint verified HTTP 200. No secret values were returned.
- Fresh `GET /readiness`: database configured true; image generation configured true; LLM configured true (`deepseek-flash`); API key configured true; legacy direct-token fields `pinterest_access_token` and `pinterest_board_id` are not configured. This is expected for the new stored-credential workflow, which reads encrypted account credentials and chooses/creates the board by name; however, the legacy `/products/{id}/content/{version}/publish` path uses the direct-token config and will not work until configured. The production `/workflow/publish-product` path using `account_id` is the working credential-based path, and it was used successfully for the single approved PB-02 Pin.
- Neon read-only inspection of `pinterest_credentials` confirmed the authorized account is `connected`, has the requested Pinterest scopes `boards:read boards:write pins:read pins:write user_accounts:read`, has an encrypted refresh token, and stored access-token expiry is 2026-11-23T16:52:50.098Z; refresh-token expiry is 2026-12-23T16:52:49Z. No credential contents were read or exposed.
- PB-03 outcome: critical runtime integrations and the credential-based publishing scopes are verified. Remaining nuance: `/readiness` is reporting the older direct-token setting as false; do not silently add unused direct-token secrets or change production environment without need. Confirm the Render service uses the intended workflow path for future publishing. Keep the discrepancy documented; only the legacy publishing endpoint is affected. No production env variables were modified.


## PB-03 readiness-code update — 2026-10-27
- Continued with the online Termux device. Current local branch is `main`, HEAD was `26a0f6c` before these uncommitted edits. Existing user changes in `CONTEXT.md` and `PB03-STATUS.md` were preserved.
- Updated `app/main.py` `/readiness` to expose `pinterest_legacy_direct_configured` separately from `pinterest_account_workflow_configured`. The old `pinterest_configured` key remains as a backward-compatible alias for the legacy direct-token route. The account workflow flag indicates only that DATABASE_URL, Pinterest token encryption key, and credential-ingest key are configured; it does not prove an account is connected or authorized.
- Added regression tests in `tests/test_api.py` for mode distinction and missing required account-workflow configuration.
- `python -m py_compile app/main.py tests/test_api.py` passed; `git diff --check` passed. Full pytest initially could not collect in Termux because the Android venv lacked `fastapi`, `httpx`, and `psycopg`. A Debian 12 / Python 3.11 environment was set up on the new Desktop Commander device; dependencies installed successfully and `pytest -q` passed: 54 passed, 1 Starlette/httpx deprecation warning.
- Fix remains local/uncommitted and is NOT deployed to Render. No Render environment variables were changed. PB-03 remains closure pending until the tested code reaches GitHub through an approved release path, the CI result for that exact commit is green, and Render deploy/readiness are verified.
- Temporary diagnostic scripts `pb03_diagnostics_safe.py` and `pb03_config_checks_safe.py` are local-only and must not be committed.
- PB-02 is closed for the one specifically approved public test Pin; do not republish it. Analytics ingestion code and descriptive evaluation are implemented and tested locally, but a real production snapshot remains unverified. Predictive ML remains deferred.

- Follow-up dependency attempt: installing full requirements in Termux failed because `cryptography`'s build backend (maturin/Rust) does not support the detected Android target in the available setup, and `psycopg-binary` has no matching Android distribution. Installing requirements without cryptography also failed dependency resolution because psycopg-binary is unavailable. This is a local test-environment/platform limitation; do not alter production dependencies just to work around it. Run CI on a supported Linux runner for authoritative tests.


## PB-03 continuation — 2026-10-27 (Debian test environment)
- New Desktop Commander device `bb54f029-ff20-4907-ad1f-8b963b1958c1` is the active testing device. Debian 12, Python 3.11.2; project at `/root/Pinterest-affiliate-marketing-agent`.
- Transferred local-only changes from the old Termux device through `/sdcard/pb03-local.patch`, applied patch on the new clone. Temporary patch file removed from working tree after apply.
- Installed full `requirements.txt` successfully in `.venv`.
- Initial dependency-complete local run passed 54 tests; after the PB-01, PB-03, PB-05 and PB-06 integration refinements, the latest combined suite is 65 passed with one Starlette/httpx TestClient deprecation warning.
- GitHub connector read-only verification works for the repo. Writing an isolated branch through the GitHub tool was blocked by the platform safety checks in the prior attempt; do not attempt to bypass that control. Git push authentication is not configured in this device shell. No changes have been pushed, and Render still runs the old deployed commit.
- Next: use an approved GitHub PR/release route (no force-push, no direct-main patch); CI must test this exact code before Render deploy. Then verify `/readiness` with authenticated request.


## PB-03 through PB-07 continuation — 2026-10-27 (latest local state)
- Active test device: Debian 12 / Python 3.11.2, Desktop Commander ID `bb54f029-ff20-4907-ad1f-8b963b1958c1`; Agent repo `/root/Pinterest-affiliate-marketing-agent`.
- PB-03 readiness separates legacy direct-token publishing, stored-OAuth publishing, and Hub-to-Agent credential-ingest configuration. It validates the AES-GCM key is valid base64 decoding to exactly 32 bytes without revealing any bytes; account workflow is not marked configured when the key is invalid. Regression tests cover the flags.
- PB-01 recovery changes from PR #15 and PB-06 fail-closed metrics validation from PR #16 were integrated locally against current deployed `main`, with conflicts resolved. PB-05 now rejects expired refresh tokens (HTTP 409) or malformed expiry values (HTTP 503) before making a provider request. Tests cover refresh-token rotation/preservation and no-secret responses.
- Agent full integrated test suite: **65 passed, 1 warning** (Starlette's deprecation warning for `httpx` in `starlette.testclient`). Syntax, compile and `git diff --check` passed. Exact combined code has not run in GitHub Actions.
- PB-04 Hub integration test is added in `/root/modern-living-hub/server/test-pinterest-agent-handoff.mjs`. It mocks Pinterest and the Agent and tests identity mapping, authenticated credential ingestion, expiry fields, stored-confirmation requirement, one-time handoff and account lookup. It passes. Hub `npm ci` now works after fixing the lockfile and upgrading multer/transitive packages; `npm audit` reports 0 vulnerabilities. Hub credential-security CI is locally updated to run this test. No real OAuth authorization was initiated.
- PB-06 live analytics snapshot and PB-05 real refresh lifecycle are still unverified against production; PB-07 production fault recovery is locally covered but not live fault-injected. No new Pin, public image, production DB mutation, Render variable change, or deployment occurred during this continuation.
- Release blocker: GitHub CLI on the new device is unauthenticated; GitHub connector branch-write was safety-blocked earlier, and PR #15 merge conflicts. Do not bypass that control. Render still runs the old commit.
