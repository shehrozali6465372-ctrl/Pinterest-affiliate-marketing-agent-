# Model 1 — Production Blockers

**Review date:** 2026-10-26  
**Repository:** Pinterest Affiliate Marketing Agent  
**Scope:** Model 1 only — Pin idea, title, description, alt text, affiliate link, image generation, publishing, and Learning Loop.

## Release decision

**Status: NOT PRODUCTION-READY for unattended/real Pin publishing.**

Read-only diagnostics previously passed for the Neon connection, a stored Pinterest account credential, Cloudflare Workers AI image generation, and DeepSeek content generation. These are useful integration checks, but they do not prove the complete publish workflow, OAuth lifecycle, analytics persistence, or failure recovery work end to end. No Pin has been published as part of the reported verification. Do not treat unverified items as passed.

## Blocker register

| ID | Priority | Status | Blocker / evidence | Required closure evidence |
|---|---|---|---|---|
| PB-01 | P0 | Open — code-level risk identified | `app/workflow.py` persists the product and content version before `_ensure_board()`. If board listing/creation fails, the idempotency key is already consumed; a retry returns 409, potentially leaving an un-published product with no publication attempt. | Add a focused regression test and change the workflow so recoverable pre-publish failures do not strand an accepted idempotency key. Verify board failure, retry, and uncertain outcomes without making a real Pin. |
| PB-02 | P0 | Open — live E2E not verified | The full `POST /workflow/publish-product` path has not been verified against all live providers in one controlled run. The endpoint can create a board and publish a Pin; diagnostics do not exercise this path. | After explicit publication approval, run a single controlled real publish with a verified product/affiliate URL, unique idempotency key, intended account and board. Confirm Pinterest returns a Pin ID and the matching Neon publication row is `succeeded`. |
| PB-03 | P0 | Open — deployment/configuration needs confirmation | The workflow requires matching production settings: `DATABASE_URL`, `PINTEREST_TOKEN_ENCRYPTION_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `LLM_API_KEY`, and `APP_API_KEY`. A successful read-only diagnostic does not prove all workflow settings and permissions are correct. | Verify configuration presence/permissions through secret-safe diagnostics; never print or commit values. Confirm encryption key decodes to exactly 32 bytes and is the same key used for the stored credential. |
| PB-04 | P1 | Open — cross-repository flow not verified end to end | Agent endpoint `POST /integrations/pinterest/credentials` accepts Hub-to-Agent credentials using `X-Credential-Ingest-Key` and encrypts tokens in Neon. A stored credential currently passes read-only account lookup, but this does not prove a fresh Modern Living Hub OAuth callback reaches this endpoint and persists the correct account. | Complete a fresh OAuth authorization in Hub; confirm the expected account metadata is stored in Neon and the Agent can perform read-only `/user_account` lookup. Verify ingest-secret agreement without exposing secrets. |
| PB-05 | P1 | Open — refresh lifecycle not live-tested | Agent refresh code calls Pinterest OAuth refresh and stores the new access token while retaining the previous refresh token if Pinterest omits a replacement. This behavior has not been confirmed with a real refresh cycle. | Use an authorized controlled refresh when appropriate; confirm response success, encrypted token persistence, subsequent `/user_account` success, and no token leakage. If refresh cannot safely be tested without disrupting the active account, document that limitation. |
| PB-06 | P1 | Open — analytics persistence not verified | `POST /learning-loop/run` selects only confirmed publications for the requested account, fetches Pinterest analytics, and upserts snapshots. With no confirmed published Pins it intentionally returns `waiting_for_published_pins`; no real snapshot has been verified. | After at least one confirmed real Pin has suitable analytics, run the Learning Loop and verify returned metrics match the Pinterest response and the expected `pin_analytics_snapshots` row. Confirm reruns update the same period rather than duplicate it. |
| PB-07 | P1 | Open — publication recovery not live-tested | The code blocks automatic retry for pending/unknown publication outcomes, but timeout, Pinterest 5xx, missing Pin ID, and failure while recording a confirmed result have not been exercised against a controlled end-to-end scenario. | Add automated failure-injection tests for timeout/5xx/missing ID and persistence failure. For any real uncertain outcome, inspect the Pinterest board and Neon record before retrying; never bypass a 409 with a new key for the same intended Pin. |
| PB-08 | P1 | Open — generated image/content quality not verified | Diagnostics confirm image generation and non-empty content fields, not that generated alt text accurately describes the final image. Current content generation supplies the generated image as an image URL/data URL, but provider success alone does not establish visual fidelity. | Inspect the exact final image and human-review title, description, and alt text for factual accuracy, policy compliance, and image consistency before first publication. |
| PB-09 | P1 | Open — affiliate destination not verified on a real Pin | The workflow validates an absolute HTTP(S) URL and passes the supplied value as the Pinterest Pin `link`, preserving its text in code. No real Pin has yet confirmed Pinterest accepted and retained the intended affiliate destination and tracking parameters. | Before publication, verify the exact destination/affiliate tracking URL is valid and allowed by the affiliate program. After the approved test publish, inspect the created Pin/API response and destination behavior; do not assume a successful request proves affiliate attribution. |
| PB-10 | P2 | Open — intermittent database behavior not root-caused | The Neon read-only query passed, and the pool uses connection checkout validation. A prior intermittent stale-connection concern has not been conclusively reproduced or root-caused. | Review production logs and reproduce with safe repeated read-only checks. Confirm pool recovery from idle disconnects and record evidence; do not label the issue fixed solely because one query passed. |
| PB-11 | P2 | Open — docs PR not merged | Documentation correction PR #11 is open at the time of this review. The current `main` README still contains stale statements such as Learning Loop returning 501 and image generation being pending, despite newer implementation code. | Merge the reviewed documentation change after validating it against current code, then confirm the default-branch README and deployed API documentation agree with the actual endpoints. |
| PB-12 | P2 | Deferred by design | Predictive ML is not implemented/trained; Learning Loop currently performs real analytics ingestion and descriptive evaluation only. This is not a defect for the current stage, but must not be marketed as predictive learning. | Keep `model_trained=false` until enough real longitudinal data exists and a model plus evaluation/monitoring pipeline is implemented and validated. |

## Verified evidence (limited)

- Previously reported live read-only diagnostics: Neon `SELECT 1`, stored Pinterest credential account lookup, Cloudflare Workers AI image generation/Base64 media-source validation, and DeepSeek content generation passed.
- Those diagnostics explicitly do not create a Pin, create a board, persist a product, or upload an image to Cloudflare Images.
- Main-branch code review confirms the product/content persistence occurs before board setup in the end-to-end workflow, creating the PB-01 retry-stranding risk.
- Main-branch code review confirms the Learning Loop only queries `pin_publications.status = 'succeeded'` with a non-null Pinterest Pin ID and account match.
- CI success is evidence for the tests that ran, not proof of live Pinterest publishing, OAuth refresh, or analytics ingestion.

## Safe execution order

1. Fix PB-01 and add regression tests on a feature branch; run CI.
2. Verify production configuration and Hub OAuth-to-Neon credential ingestion without exposing secrets.
3. Add/execute non-publishing failure-injection tests for publish recovery.
4. Review the actual generated image and metadata; validate the affiliate destination.
5. Obtain explicit approval before any real publish. Perform one controlled publish only after PB-01 is closed.
6. Verify the returned Pin ID and Neon publication record, then verify analytics snapshot ingestion when Pinterest data is available.
7. Resolve the docs PR and investigate the intermittent database concern.
8. Keep predictive ML deferred until there is sufficient real analytics history.

## Safety rules

- No mock data or fabricated analytics may be represented as production evidence.
- Never expose API keys, OAuth tokens, encryption keys, or ingest secrets in chat, logs, or repository files.
- Do not create a real Pin or board as part of diagnostics. Real publication requires explicit user approval.
- An uncertain Pinterest publish result must be reconciled against Pinterest and Neon before any retry.
