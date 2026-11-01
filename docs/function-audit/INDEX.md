# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0
Audit documentation HEAD at this refresh: 6faa0e246a84a48b8f5161a2c7e23e178ff89271
Mode: READ-ONLY static source audit and documentation. No application code, production DB, credentials, provider state, deployment or Pinterest Pins changed.

## Inventory

- Python files under app/, scripts/ and tests/: 30.
- Production Python files (app/ + scripts/): 13.
- Test modules: 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Audit Markdown files: 242 (241 records excluding index).
- FN-prefixed definition records: 94.
- TEST-prefixed records: 136.
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
4. Mapped each test module to production surfaces and classified mocked/unit vs opt-in PostgreSQL integration evidence in TEST-TO-PRODUCTION-MAP.md.
5. Reviewed all eight SQL migrations statement-by-statement in MIGRATIONS-001-008.md.
6. Reviewed all five GitHub Actions workflows step-by-step in WORKFLOWS-001-005.md.
7. Recorded the inventory, counts, call graph, prioritized findings and verification boundaries in COVERAGE-MATRIX-AND-FINAL-FINDINGS.md.

## Prioritized source findings

- P1: Refresh endpoint is separate; normal workflow/Learning Loop paths retrieve and use access tokens directly. Automatic refresh is not wired into those paths.
- P1: End-to-end workflow may create a Pinterest board before later provider generation and persistence finish.
- P1: Ambiguous Pinterest writes require unknown-state handling and operator verification; no blind retry.
- P2: Learning Loop ingests real analytics and computes descriptive aggregates; it explicitly returns model_trained=false. Predictive ML training is not implemented.
- P2: Product name/details are caller inputs; product research/extraction from affiliate URL is not present in this baseline.
- P2: POST /diagnostics/run invokes Cloudflare Workers AI and DeepSeek generation; provider usage may be billable.
- P2: Pinterest account operation route exposes create_board/create_pin outside publication ledger controls.
- P3: Legacy publication rows remain NULL account_id after migration 007.
- P3: Board resolver reads at most the first 100 boards and does not paginate.

## Completion and evidence boundary

**Static source audit: COMPLETE** for the recorded application baseline: definitions inventoried and reviewed at module/function level; test functions and helpers reviewed; call graph, test mapping, migrations, workflows and prioritized findings documented.

**Runtime/production verification: NOT PERFORMED.** No test suite was run in this continuation, no workflow dispatched, no live provider/OAuth call made, no DB query/migration performed, and no real Pin published. The opt-in PostgreSQL recovery test terminates a backend session and was not run. Existing CI run evidence must be checked against an exact run ID/commit before being treated as current proof.

Do not interpret static source review as proof that Render runs this baseline, Neon schema is current, secrets are configured, provider credentials work, or Pinterest operations succeed live. Any live diagnostic that invokes generation may incur cost and requires separate approval. No production write, deploy, credential mutation or Pin publication is authorized by this audit.
