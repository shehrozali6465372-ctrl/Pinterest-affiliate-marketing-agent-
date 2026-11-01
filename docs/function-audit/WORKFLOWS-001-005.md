# GitHub Actions workflow audit — all five workflows

Baseline: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`. YAML source fetched and reviewed; workflows were not dispatched by this audit.

## 1. `.github/workflows/ci.yml` — Python CI

Runs on pushes to main and `fix/pb06-analytics-forward-port`, pull requests to main, or manual dispatch. Grants contents:read. Ubuntu runner provisions PostgreSQL 16 service with health check, installs dependencies on Python 3.11, sets TEST_DATABASE_URL to local service and runs full pytest. Static risk: no explicit workflow timeout; test DB is ephemeral service. A green run proves only the tested commit and its configured local-Postgres tests.

## 2. `.github/workflows/pinterest-learning-loop.yml` — scheduled analytics ingestion

Runs daily at 03:17 UTC and manually; concurrency prevents overlap. Calls the production Learning Loop POST with GitHub secret API key and configured/default account ID; validates key and ID format, enforces 100-second curl timeout, and prints a whitelisted response summary. It ingests real analytics and persists snapshots through application route; it is not model training because application response explicitly reports model_trained false. It is a production DB write and Pinterest analytics read, although it does not publish Pins. Failure output attempts to whitelist safe metadata.

## 3. `.github/workflows/read-only-production-verification.yml` — read-only verification

Manual dispatch with publication_id input (default 1). Calls protected GET readiness and provider diagnostics, then GET publication Pinterest verification. Summary whitelists configuration/provider fields and flags no secrets, generation, Pinterest write or DB mutation for the first checks; publication verification paginates board pins and reads Pin detail. Workflow expects complete pagination and validates stored Pin/board match for succeeded publications. Note: this workflow's provider endpoint is described as non-billable in its comments; actual cost/side effects must be checked against implementation and provider contracts, not assumed from workflow naming.

## 4. `.github/workflows/safe-production-diagnostics.yml` — provider diagnostics

Manual dispatch only; validates secret and account ID, then POSTs to `/diagnostics/run` with a synthetic kitchen product. The endpoint's implementation invokes Cloudflare image generation and DeepSeek content generation; Cloudflare Images upload/provider usage may be billable. Workflow checks explicit side-effect flags and secrets_returned false, but these checks occur after the provider calls. It asserts no Pinterest Pin/board and no product persistence, but requires `cloudflare_test_image_uploaded=false`; whether that matches current implementation must be verified at route level. This workflow is not cost-free and should not be treated as a harmless read-only probe.

## 5. `.github/workflows/tests.yml` — Python tests

Runs on pull requests and pushes to main; contents:read; Ubuntu, Python 3.12, installs requirements and runs pytest. It does not provision PostgreSQL or set TEST_DATABASE_URL, so tests guarded by that environment may skip. This differs from ci.yml (Python 3.11 plus PostgreSQL 16 service). A pass in one workflow is not equivalent to a pass in the other.

## Cross-workflow findings

- Two independent CI workflows have materially different Python versions and database integration setup; report the exact workflow/run when citing a green test.
- The scheduled Learning Loop is a production write to analytics storage, not a predictive learning/training pipeline.
- The safe diagnostics workflow triggers real provider generation and can incur cost despite not publishing a Pin. The read-only verification workflow is the safer choice for non-generative checks.
- None of these YAML reviews proves a workflow currently has valid secrets, is enabled, or succeeded at runtime. No workflow was dispatched during this audit.