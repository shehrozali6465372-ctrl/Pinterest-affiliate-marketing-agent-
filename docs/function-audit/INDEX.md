# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0
Audit documentation HEAD at this refresh: ae95b48759e977cb7fde30709c91d9fd70b8f658
Mode: READ-ONLY static source audit and documentation. No application code, production DB, credentials, provider state, deployment or Pinterest Pins changed.

## Inventory and documentation counts

- Python files under app/, scripts/ and tests/: 30.
- Test modules: 17.
- SQL migrations: 8.
- GitHub Actions workflows: 5.
- Audit Markdown files: 234 (233 records excluding this index).
- FN-prefixed definition records: 94.
- TEST-prefixed records: 135, including 119 individual top-level test-function records plus grouped/helper/review records.
- Duplicate FN-/TEST- record IDs: 0.

## Completed static review

1. All 30 Python files under app/, scripts/ and tests/ were enumerated. Application definitions were inventoried and individual FN records exist for the production classes/functions/helpers, with an overall production call graph and prioritized source-level findings in PRODUCTION-CALL-GRAPH-AND-RISK-REVIEW.md.
2. All 119 top-level test functions across 17 test modules have individual TEST records. Test helper/fixture/fake-client behavior and limitations are covered in grouped TEST-HELPERS-* reviews.
3. All eight SQL migrations were reviewed statement-by-statement in MIGRATIONS-001-008.md.
4. All five GitHub Actions workflows were reviewed step-by-step in WORKFLOWS-001-005.md.
5. COVERAGE-MATRIX-AND-FINAL-FINDINGS.md contains the inventory, test counts, call graph, prioritized findings and explicit evidence limits.

## Principal findings

- Refresh endpoint exists, but normal workflow/Learning Loop request paths directly retrieve and use access tokens; automatic refresh invocation is not wired in the audited paths.
- End-to-end workflow may create a Pinterest board before image/content generation and product persistence complete.
- Ambiguous Pinterest writes require unknown-state handling and operator verification; never blindly retry.
- Learning Loop persists real Pinterest analytics and descriptive aggregates, but explicitly reports model_trained=false; no ML training is implemented.
- Product research/extraction from affiliate URL is not demonstrated; name/details are caller-supplied.
- POST /diagnostics/run calls Cloudflare Workers AI and DeepSeek generation and may incur provider usage.
- Pinterest account operation route contains create_board/create_pin operations outside the publication ledger.
- Legacy publication rows have NULL account_id after migration 007.
- Board resolver checks at most the first 100 boards; no pagination is implemented in that helper.

## Remaining work — exhaustive function-by-function task is not yet fully complete

- The inventory and individual FN records exist, but several FN documents remain generic templates or UNVERIFIED and do not yet provide complete statement-by-statement explanation, full caller/callee trace and mapped assertions for every production definition.
- Grouped helper reviews cover nested test fakes/fixtures, but do not split every nested method into its own record.
- The audit has not executed the test suite or re-verified current GitHub Actions runs in this continuation.
- No runtime provider, OAuth, production database, migration, deployment or publishing checks were performed. The disposable PostgreSQL integration test is destructive to a backend session and was not run.

Do not claim the entire task complete until each FN record has a substantive function-specific explanation and caller/callee/test mapping, and runtime checks (if separately approved) are reported against exact commit/run IDs. No live Pin publish or production mutation is authorized by this audit.
