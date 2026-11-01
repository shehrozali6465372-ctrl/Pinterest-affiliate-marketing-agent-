# Per-function audit index — Model 1

Repository: `shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-`
Branch: `main`
Snapshot: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
Mode: **READ ONLY** — application source, settings, secrets, services, databases and Pinterest untouched.

Each of 91 entries below has one isolated Python definition per Markdown file, a unique ID, unique filename, exact source line range and source blob SHA.

**Status legend:** `VERIFIED — SOURCE PRESENT` confirms only source existence. `UNVERIFIED — LOGIC` means correctness, call graph, tests and runtime semantics are not yet proved. Source existence alone is not behavioral verification.

## Python definitions

1. `docs/function-audit/FN-APP-CONFIG-PY-001__settings.md`
2. `docs/function-audit/FN-APP-CONFIG-PY-002__clean-secret-values.md`
3. `docs/function-audit/FN-APP-CONTENT-GENERATION-PY-001__generatedcontent.md`
4. `docs/function-audit/FN-APP-CONTENT-GENERATION-PY-002__contentgenerationerror.md`
5. `docs/function-audit/FN-APP-CONTENT-GENERATION-PY-003__safe-http-failure-metadata.md`
6. `docs/function-audit/FN-APP-CONTENT-GENERATION-PY-004__sanitize.md`
7. `docs/function-audit/FN-APP-CONTENT-GENERATION-PY-005__generate-pin-content.md`
8. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-001__tokenencryptionconfigurationerror.md`
9. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-002__cipher.md`
10. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-003__token-encryption-key-is-valid.md`
11. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-004__encrypt.md`
12. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-005__store-pinterest-credential.md`
13. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-006__get-pinterest-credential.md`
14. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-007__get-pinterest-refresh-credential.md`
15. `docs/function-audit/FN-APP-CREDENTIAL-VAULT-PY-008__revoke-pinterest-credential.md`
16. `docs/function-audit/FN-APP-DATABASE-PY-001__databaseconfigurationerror.md`
17. `docs/function-audit/FN-APP-DATABASE-PY-002__get-pool.md`
18. `docs/function-audit/FN-APP-DATABASE-PY-003__connection.md`
19. `docs/function-audit/FN-APP-DATABASE-PY-004__run-migrations.md`
20. `docs/function-audit/FN-APP-DATABASE-PY-005__get-product-by-idempotency-key.md`
21. `docs/function-audit/FN-APP-DATABASE-PY-006__create-product.md`
22. `docs/function-audit/FN-APP-DATABASE-PY-007__get-product.md`
23. `docs/function-audit/FN-APP-DATABASE-PY-008__create-content-version.md`
24. `docs/function-audit/FN-APP-DATABASE-PY-009__create-product-with-content-version.md`
25. `docs/function-audit/FN-APP-DATABASE-PY-010__get-content-version.md`
26. `docs/function-audit/FN-APP-DATABASE-PY-011__list-content-versions.md`
27. `docs/function-audit/FN-APP-DATABASE-PY-012__begin-publish-attempt.md`
28. `docs/function-audit/FN-APP-DATABASE-PY-013__finish-publish-attempt.md`
29. `docs/function-audit/FN-APP-DATABASE-PY-014__get-publication.md`
30. `docs/function-audit/FN-APP-DATABASE-PY-015__reconcile-unknown-publication.md`
31. `docs/function-audit/FN-APP-DATABASE-PY-016__close-pool.md`
32. `docs/function-audit/FN-APP-DIAGNOSTICS-PY-001__require-api-key.md`
33. `docs/function-audit/FN-APP-DIAGNOSTICS-PY-002__database-diagnostic.md`
34. `docs/function-audit/FN-APP-DIAGNOSTICS-PY-003__pinterest-read-only-diagnostic.md`
35. `docs/function-audit/FN-APP-DIAGNOSTICS-PY-004__diagnosticruninput.md`
36. `docs/function-audit/FN-APP-DIAGNOSTICS-PY-005__run-live-diagnostics.md`
37. `docs/function-audit/FN-APP-LEARNING-PY-001__require-api-key.md`
38. `docs/function-audit/FN-APP-LEARNING-PY-002__learningrequest.md`
39. `docs/function-audit/FN-APP-LEARNING-PY-003__number.md`
40. `docs/function-audit/FN-APP-LEARNING-PY-004__run-learning-loop.md`
41. `docs/function-audit/FN-APP-MAIN-PY-001__lifespan.md`
42. `docs/function-audit/FN-APP-MAIN-PY-002__require-api-key.md`
43. `docs/function-audit/FN-APP-MAIN-PY-003__require-configured-api-key.md`
44. `docs/function-audit/FN-APP-MAIN-PY-004__productinput.md`
45. `docs/function-audit/FN-APP-MAIN-PY-005__strip-required-text.md`
46. `docs/function-audit/FN-APP-MAIN-PY-006__validate-affiliate-url-without-rewriting.md`
47. `docs/function-audit/FN-APP-MAIN-PY-007__pinterestcredentialinput.md`
48. `docs/function-audit/FN-APP-MAIN-PY-008__publishrequest.md`
49. `docs/function-audit/FN-APP-MAIN-PY-009__serialize-row.md`
50. `docs/function-audit/FN-APP-MAIN-PY-010__health.md`
51. `docs/function-audit/FN-APP-MAIN-PY-011__readiness.md`
52. `docs/function-audit/FN-APP-MAIN-PY-012__provider-diagnostics.md`
53. `docs/function-audit/FN-APP-MAIN-PY-013__ingest-pinterest-credential.md`
54. `docs/function-audit/FN-APP-MAIN-PY-014__pinterestrefreshinput.md`
55. `docs/function-audit/FN-APP-MAIN-PY-015__pinterestoperationinput.md`
56. `docs/function-audit/FN-APP-MAIN-PY-016__refresh-pinterest-credential.md`
57. `docs/function-audit/FN-APP-MAIN-PY-017__pinterest-account-operation.md`
58. `docs/function-audit/FN-APP-MAIN-PY-018__validate-product.md`
59. `docs/function-audit/FN-APP-MAIN-PY-019__create-product.md`
60. `docs/function-audit/FN-APP-MAIN-PY-020__read-product.md`
61. `docs/function-audit/FN-APP-MAIN-PY-021__generate-product-content.md`
62. `docs/function-audit/FN-APP-MAIN-PY-022__list-product-content.md`
63. `docs/function-audit/FN-APP-MAIN-PY-023__publicationreconciliationinput.md`
64. `docs/function-audit/FN-APP-MAIN-PY-024__evidence-must-be-nonblank.md`
65. `docs/function-audit/FN-APP-MAIN-PY-025__get-publication-status.md`
66. `docs/function-audit/FN-APP-MAIN-PY-026__verify-publication-on-pinterest.md`
67. `docs/function-audit/FN-APP-MAIN-PY-027__reconcile-publication.md`
68. `docs/function-audit/FN-APP-MAIN-PY-028__publish-product-content.md`
69. `docs/function-audit/FN-APP-MAIN-PY-029__publish.md`
70. `docs/function-audit/FN-APP-MAIN-PY-030__learning-loop-unavailable.md`
71. `docs/function-audit/FN-APP-MEDIA-GENERATION-PY-001__imagegenerationerror.md`
72. `docs/function-audit/FN-APP-MEDIA-GENERATION-PY-002__cloudflare-error-codes.md`
73. `docs/function-audit/FN-APP-MEDIA-GENERATION-PY-003__safe-cloudflare-error.md`
74. `docs/function-audit/FN-APP-MEDIA-GENERATION-PY-004__generate-and-host-pin-image.md`
75. `docs/function-audit/FN-APP-PINTEREST-PY-001__pinterestpublisherror.md`
76. `docs/function-audit/FN-APP-PINTEREST-PY-002__init.md`
77. `docs/function-audit/FN-APP-PINTEREST-PY-003__image-media-source.md`
78. `docs/function-audit/FN-APP-PINTEREST-PY-004__publish-image-pin.md`
79. `docs/function-audit/FN-APP-PINTEREST-PY-005__pinterestreaderror.md`
80. `docs/function-audit/FN-APP-PINTEREST-PY-006__list-board-pins-read-only.md`
81. `docs/function-audit/FN-APP-PINTEREST-PY-007__get-pin-read-only.md`
82. `docs/function-audit/FN-APP-PROVIDER-RETRY-PY-001__retry-delay-seconds.md`
83. `docs/function-audit/FN-APP-WORKFLOW-PY-001__require-api-key.md`
84. `docs/function-audit/FN-APP-WORKFLOW-PY-002__log-workflow-failure.md`
85. `docs/function-audit/FN-APP-WORKFLOW-PY-003__productworkflowinput.md`
86. `docs/function-audit/FN-APP-WORKFLOW-PY-004__nonblank.md`
87. `docs/function-audit/FN-APP-WORKFLOW-PY-005__valid-destination.md`
88. `docs/function-audit/FN-APP-WORKFLOW-PY-006__pinterest-request.md`
89. `docs/function-audit/FN-APP-WORKFLOW-PY-007__ensure-board.md`
90. `docs/function-audit/FN-APP-WORKFLOW-PY-008__publish-product-end-to-end.md`
91. `docs/function-audit/FN-SCRIPTS-MIGRATE-PY-001__main.md`

Coverage: 91 definitions across 12 Python source files. Tests, workflows, SQL migrations, dependency manifests, README/context and other assets are additional audit surfaces. Full repository audit is not yet complete.