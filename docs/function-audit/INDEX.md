# Function audit index — Model 1

Repository: shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-
Branch: main
Current docs head before index update: 4161e67d5192a6b8b71a598b89b528ccf471e639
Application source baseline: 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0
Mode: READ-ONLY ANALYSIS. No application code, production DB, credentials, provider state, deployment or Pinterest Pins were changed.

## Current audit artefacts

Separate audit/review Markdown files present (excluding this index): 90

- docs/function-audit/FN-APP-CONFIG-PY-001__settings.md
- docs/function-audit/FN-APP-CONFIG-PY-002__clean-secret-values.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-001__generatedcontent.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-002__contentgenerationerror.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-003__-safe-http-failure-metadata.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-003__safe-http-failure-metadata.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-004__sanitize.md
- docs/function-audit/FN-APP-CONTENT-GENERATION-PY-005__generate-pin-content.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-001__tokenencryptionconfigurationerror.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-002__-cipher.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-003__token-encryption-key-is-valid.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-004__-encrypt.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-005__store-pinterest-credential.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-006__get-pinterest-credential.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-007__get-pinterest-refresh-credential.md
- docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-008__revoke-pinterest-credential.md
- docs/function-audit/FN-APP-DATABASE-PY-002__get-pool.md
- docs/function-audit/FN-APP-DATABASE-PY-003__connection.md
- docs/function-audit/FN-APP-DATABASE-PY-004__run-migrations.md
- docs/function-audit/FN-APP-DATABASE-PY-005__get-product-by-idempotency-key.md
- docs/function-audit/FN-APP-DATABASE-PY-006__create-product.md
- docs/function-audit/FN-APP-DATABASE-PY-007__get-product.md
- docs/function-audit/FN-APP-DATABASE-PY-008__create-content-version.md
- docs/function-audit/FN-APP-DATABASE-PY-009__create-product-with-content-version.md
- docs/function-audit/FN-APP-DATABASE-PY-010__get-content-version.md
- docs/function-audit/FN-APP-DATABASE-PY-011__list-content-versions.md
- docs/function-audit/FN-APP-DATABASE-PY-012__begin-publish-attempt.md
- docs/function-audit/FN-APP-DATABASE-PY-013__finish-publish-attempt.md
- docs/function-audit/FN-APP-DATABASE-PY-014__get-publication.md
- docs/function-audit/FN-APP-DATABASE-PY-015__reconcile-unknown-publication.md
- docs/function-audit/FN-APP-DATABASE-PY-016__close-pool.md
- docs/function-audit/FN-APP-DIAGNOSTICS-PY-001__require-api-key.md
- docs/function-audit/FN-APP-DIAGNOSTICS-PY-002__database-diagnostic.md
- docs/function-audit/FN-APP-DIAGNOSTICS-PY-003__pinterest-read-only-diagnostic.md
- docs/function-audit/FN-APP-DIAGNOSTICS-PY-004__diagnostic-run-input.md
- docs/function-audit/FN-APP-DIAGNOSTICS-PY-005__run-live-diagnostics.md
- docs/function-audit/FN-APP-LEARNING-PY-001__require-api-key.md
- docs/function-audit/FN-APP-LEARNING-PY-002__learningrequest.md
- docs/function-audit/FN-APP-LEARNING-PY-003__number.md
- docs/function-audit/FN-APP-LEARNING-PY-004__run-learning-loop.md
- docs/function-audit/FN-APP-MAIN-PY-001__lifespan.md
- docs/function-audit/FN-APP-MAIN-PY-002__require-api-key.md
- docs/function-audit/FN-APP-MAIN-PY-003__require-configured-api-key.md
- docs/function-audit/FN-APP-MAIN-PY-004__productinput.md
- docs/function-audit/FN-APP-MAIN-PY-005__strip-required-text.md
- docs/function-audit/FN-APP-MAIN-PY-006__validate-affiliate-url-without-rewriting.md
- docs/function-audit/FN-APP-MAIN-PY-007__pinterestcredentialinput.md
- docs/function-audit/FN-APP-MAIN-PY-008__publishrequest.md
- docs/function-audit/FN-APP-MAIN-PY-009__-serialize-row.md
- docs/function-audit/FN-APP-MAIN-PY-009__serialize-row.md
- docs/function-audit/FN-APP-MAIN-PY-010__health.md
- docs/function-audit/FN-APP-MAIN-PY-011__readiness.md
- docs/function-audit/FN-APP-MAIN-PY-012__provider-diagnostics.md
- docs/function-audit/FN-APP-MAIN-PY-013__ingest-pinterest-credential.md
- docs/function-audit/FN-APP-MAIN-PY-014__pinterestrefreshinput.md
- docs/function-audit/FN-APP-MAIN-PY-015__pinterestoperationinput.md
- docs/function-audit/FN-APP-MAIN-PY-016__refresh-pinterest-credential.md
- docs/function-audit/FN-APP-MAIN-PY-017__pinterest-account-operation.md
- docs/function-audit/FN-APP-MAIN-PY-018__validate-product.md
- docs/function-audit/FN-APP-MAIN-PY-019__create-product.md
- docs/function-audit/FN-APP-MAIN-PY-020__read-product.md
- docs/function-audit/FN-APP-MAIN-PY-021__generate-product-content.md
- docs/function-audit/FN-APP-MAIN-PY-022__list-product-content.md
- docs/function-audit/FN-APP-MAIN-PY-023__publicationreconciliationinput.md
- docs/function-audit/FN-APP-MAIN-PY-024__evidence-must-be-nonblank.md
- docs/function-audit/FN-APP-MAIN-PY-025__get-publication-status.md
- docs/function-audit/FN-APP-MAIN-PY-026__verify-publication-on-pinterest.md
- docs/function-audit/FN-APP-MAIN-PY-027__reconcile-publication.md
- docs/function-audit/FN-APP-MAIN-PY-028__publish-product-content.md
- docs/function-audit/FN-APP-MAIN-PY-029__publish.md
- docs/function-audit/FN-APP-MAIN-PY-030__learning-loop-unavailable.md
- docs/function-audit/FN-APP-MEDIA-GENERATION-PY-001__imagegenerationerror.md
- docs/function-audit/FN-APP-MEDIA-GENERATION-PY-002__-cloudflare-error-codes.md
- docs/function-audit/FN-APP-MEDIA-GENERATION-PY-003__-safe-cloudflare-error.md
- docs/function-audit/FN-APP-MEDIA-GENERATION-PY-004__generate-and-host-pin-image.md
- docs/function-audit/FN-APP-PINTEREST-PY-003__image-media-source.md
- docs/function-audit/FN-APP-PINTEREST-PY-004__publish-image-pin.md
- docs/function-audit/FN-APP-PINTEREST-PY-006__list-board-pins-read-only.md
- docs/function-audit/FN-APP-PINTEREST-PY-007__get-pin-read-only.md
- docs/function-audit/FN-APP-PROVIDER-RETRY-PY-001__retry-delay-seconds.md
- docs/function-audit/FN-APP-WORKFLOW-PY-001__require-api-key.md
- docs/function-audit/FN-APP-WORKFLOW-PY-002__log-workflow-failure.md
- docs/function-audit/FN-APP-WORKFLOW-PY-003__productworkflowinput.md
- docs/function-audit/FN-APP-WORKFLOW-PY-004__nonblank.md
- docs/function-audit/FN-APP-WORKFLOW-PY-005__valid-destination.md
- docs/function-audit/FN-APP-WORKFLOW-PY-006__pinterest-request.md
- docs/function-audit/FN-APP-WORKFLOW-PY-007__-ensure-board.md
- docs/function-audit/FN-APP-WORKFLOW-PY-008__publish-product-end-to-end.md
- docs/function-audit/FN-SCRIPTS-MIGRATE-PY-001__main.md
- docs/function-audit/TEST-REVIEW-001__publication-learning-token-refresh.md

## Verification tag policy

- VERIFIED — SOURCE PRESENT: exact source fetched from GitHub.
- VERIFIED — DEFINITION ISOLATION: one definition boundary and line range checked.
- VERIFIED — ASSERTION MAPPING: a named test assertion was inspected and mapped to a behavior.
- VERIFIED — STATIC LOGIC: caller/callee and branches traced sufficiently for the stated claim.
- VERIFIED — LIVE BEHAVIOR: only when a safe, approved runtime check proves it.
- UNVERIFIED: evidence incomplete, indirect or absent.

Source presence is not behavioral verification. Mocked tests do not prove real provider behavior. No publish-capable route is invoked in this audit.

## Repository coverage and remaining work

Initial scan covered Python files under app/ and scripts/, 17 test modules, eight SQL migrations and five GitHub Actions workflow files. Each remaining function/class/validator—including nested test helpers—still needs its own unique record. Some early records are preliminary and need line-by-line expansion; the record count is not a completion percentage.

Remaining sequence:
1. Complete all missing source definition records; one definition per file, unique ID and filename.
2. Expand every record to line-by-line explanation of inputs, defaults, validation, branches, loops, calls, DB writes, returns and exceptions.
3. Trace call graph and data flow across the full production workflow.
4. Audit all test functions and map assertions to production behavior; separate mocks from real integration tests.
5. Inspect every migration, constraint, index, state transition and transaction boundary.
6. Inspect all CI/CD workflows for permissions, triggers, secrets, scheduled actions and possible publishing/deployment effects.
7. Reconcile README, CONTEXT, PB status, requirements and .env.example against code.
8. Produce final coverage matrix and risk register. Unproven claims remain UNVERIFIED.

No implementation, refactor, test execution, production diagnostic, migration, secret rotation, deployment, merge or Pin publishing is in scope.