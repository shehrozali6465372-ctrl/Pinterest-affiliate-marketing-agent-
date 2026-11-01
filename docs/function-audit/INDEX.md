# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0
Audit documentation baseline before reconciliation: b11ab14dfce4bc2236f67806806914cf219ac5d3; see latest main commit for the reconciled index.
Mode: READ-ONLY static source audit and documentation. No application code, production DB, credentials, provider state, deployment or Pinterest Pins changed.

## Inventory

- Python files under app/, scripts/ and tests/: 30.
- Production Python files (app/ + scripts/): 13.
- Test modules: 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Audit Markdown files: 242 at docs/function-audit/ root (241 records excluding index); three previously misplaced reports were restored from a nested docs/function-audit/docs/function-audit/ directory.
- FN-prefixed definition records: 94.
- TEST-prefixed records: 135.
- Top-level test functions documented individually: 119/119.
- Duplicate FN-/TEST- record IDs: 0.

## Completed static audit scope

1. Enumerated Python definitions across all 30 Python files.
2. Added individual FN records for production classes/functions/helpers and expanded function-specific explanations in:
   - PRODUCTION-DETAIL-MAIN-ROUTES.md
   - PRODUCTION-DETAIL-DATABASE.md
   - PRODUCTION-DETAIL-CREDENTIAL-VAULT.md
   - PRODUCTION-DETAIL-WORKFLOW.md
   - PRODUCTION-DETAIL-LEARNING.md
   - PRODUCTION-DETAIL-CONTENT-MEDIA-PINTEREST.md
   - PRODUCTION-DETAIL-REMAINING-MODULES.md
   - PRODUCTION-CALL-GRAPH-AND-RISK-REVIEW.md
3. Documented all 119 top-level test functions individually; reviewed nested helpers/fakes/fixtures in grouped TEST-HELPERS-* documents.
4. Restored PRODUCTION-DETAIL-REMAINING-MODULES.md and TEST-TO-PRODUCTION-MAP.md from the nested docs/function-audit/docs/function-audit/ directory to the audit root so the index links resolve.
5. Reviewed all eight SQL migrations statement-by-statement in MIGRATIONS-001-008.md.
6. Reviewed all five GitHub Actions workflows step-by-step in WORKFLOWS-001-005.md.
7. Recorded the inventory, counts, call graph, prioritized findings and verification boundaries in COVERAGE-MATRIX-AND-FINAL-FINDINGS.md.

## Prioritized source findings

- P1: Routes using require_api_key are accessible when APP_API_KEY is unset; this dependency is not fail-closed. In particular, product persistence and content-generation routes use it. Publish routes use require_configured_api_key, and diagnostics/learning routers have their own fail-closed checks.
- P1: Refresh endpoint is separate; normal workflow/Learning Loop paths retrieve and use access tokens directly. Automatic refresh is not wired into those paths. Refresh-token rotation is also not serialized per account.
- P1: End-to-end workflow may create a Pinterest board before later provider generation and persistence finish.
- P1: Ambiguous Pinterest writes require unknown-state handling and operator verification; no blind retry.
- P2: Learning Loop ingests real analytics and computes descriptive aggregates; it explicitly returns model_trained=false. Predictive ML training is not implemented.
- P2: Product name/details are caller inputs; product research/extraction from affiliate URL is not present in this baseline.
- P2: POST /diagnostics/run invokes Cloudflare Workers AI and DeepSeek generation; provider usage may be billable.
- P2: Pinterest account operation route exposes create_board/create_pin outside publication ledger controls.
- P3: Legacy publication rows remain NULL account_id after migration 007.
- P3: Board resolver reads at most the first 100 boards and does not paginate.

## Completion and evidence boundary

**Static source audit: COMPLETE at module/function level** for the recorded application baseline. Definitions are inventoried; production modules, all top-level test functions, grouped test helpers, migrations, workflows, call graph and prioritized findings are documented. The coverage matrix explicitly records review boundaries and does not claim a separate statement-by-statement trace for every nested helper.

**Runtime/production verification: NOT PERFORMED.** No test suite was run in this continuation, no workflow dispatched, no live provider/OAuth call made, no DB query/migration performed, and no real Pin published. The audit commit had no combined status entries and no commit-associated workflow runs returned at verification time; this is neither a pass nor a fail. The opt-in PostgreSQL recovery test terminates a backend session and was not run. Existing CI run evidence must be checked against an exact run ID/commit before being treated as current proof.

See COVERAGE-MATRIX-AND-FINAL-FINDINGS.md for the reconciled coverage matrix, prioritized remediation order and source findings. The test-to-production map and remaining-module review are now present at the paths linked by this index. Do not interpret static source review as proof that Render runs this baseline, Neon schema is current, secrets are configured, provider credentials work, or Pinterest operations succeed live. Any live diagnostic that invokes generation may incur cost and requires separate approval. No production write, deploy, credential mutation or Pin publication is authorized by this audit.
