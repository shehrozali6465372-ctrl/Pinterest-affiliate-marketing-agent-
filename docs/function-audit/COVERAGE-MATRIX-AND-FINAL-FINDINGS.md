# Coverage matrix and final findings — Model 1 function audit

Repository: `shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-`
Branch: `main`
Audit documentation commit at preparation: `b11ab14dfce4bc2236f67806806914cf219ac5d3`
Application source baseline reviewed: `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
Mode: read-only source review. No code behavior, production data, credentials, deployment or Pins changed.

## Coverage inventory (source/index records)

| Area | Inventory | Review evidence | Runtime evidence |
|---|---:|---|---|
| Python | 30 files under app/, scripts/, tests/ | Definitions inventoried; production modules reviewed in dedicated detail reports; 119 top-level test functions have individual TEST records | Not run in this audit |
| Production Python | 13 files under app/ and scripts/ | Dedicated reviews for main routes, database, credential vault, workflow, learning, content/media/Pinterest and remaining modules | Not live-verified |
| Tests | 17 modules; 119 top-level test functions | TEST records and grouped helper/fake/fixture reviews; TEST-TO-PRODUCTION-MAP is referenced by index but was not retrievable at the checked path | No test suite run |
| SQL | 8 migrations | MIGRATIONS-001-008.md reviewed statement-by-statement | No migration executed |
| GitHub Actions | 5 workflows | WORKFLOWS-001-005.md reviewed step-by-step | No workflow dispatched |
| Audit documents | Index reports 242 Markdown files (241 records excluding index) | Counts are index-reported; this audit refresh did not independently enumerate the complete Git tree | N/A |

## Production call-path summary

1. FastAPI app is composed in `app/main.py`; workflow, diagnostics and learning routers are included.
2. Hub-to-Agent OAuth credential ingestion uses `X-Credential-Ingest-Key`; access and refresh tokens are encrypted with AES-GCM before Neon persistence.
3. Stored credential reads decrypt the token for trusted server-side requests.
4. Refresh is a separate service-key route. Main workflow and Learning Loop retrieve access tokens directly; no shared automatic expiry-aware refresh dependency is wired into those paths.
5. Product/content routes accept product name/details from the caller. No affiliate URL product extraction/research is present in the reviewed baseline.
6. End-to-end workflow can create a Pinterest board before later generation/persistence completes, then persists product/content, reserves a publication attempt and sends Pinterest POST /pins.
7. Pinterest analytics snapshots are ingested and aggregated by Learning Loop. It returns `model_trained=false`; no model training or adaptive policy update is implemented.
8. `POST /diagnostics/run` calls Cloudflare Workers AI and DeepSeek generation after prerequisites succeed; this may consume provider credits.
9. The direct Pinterest operation route includes create_board/create_pin outside the publication ledger.

## Prioritized source findings

### P1 — Inconsistent fail-closed API authentication

In `app/main.py`, `require_api_key` returns successfully when `APP_API_KEY` is absent. `require_configured_api_key` fails closed, but only routes that explicitly use that dependency benefit. The diagnostics and learning routers implement their own fail-closed checks. Audit every operational route and ensure any sensitive or state-changing route uses a fail-closed dependency. Do not rely on a missing secret to protect an endpoint.

### P1 — Refresh-token rotation race and missing automatic refresh

The refresh endpoint is separate and no per-account refresh lock is evident in the credential vault/refresh route. Concurrent refreshes can race if Pinterest rotates refresh tokens. Ordinary publish/analytics paths do not automatically refresh on expiry/401. Add a per-account lock and carefully bounded refresh policy before claiming unattended OAuth recovery.

### P1 — Board creation precedes workflow completion

The end-to-end workflow may create a board before provider generation and product persistence. A later failure can leave an orphan board. The board resolver only checks the first 100 boards, so it can miss an existing board on a later page and create a duplicate.

### P1 — Ambiguous Pin writes require reconciliation

Transport errors, server errors, malformed responses or missing Pin IDs can leave a write outcome uncertain. Preserve unknown state and operator verification. Never blindly retry a potentially successful POST /pins.

### P2 — Learning Loop is analytics ingestion, not ML training

It reads Pin analytics, stores snapshots and calculates descriptive aggregates. `model_trained=false` is explicit. Predictive training/adaptive optimization requires a defined dataset, labels/features, evaluation, model versioning and promotion/rollback gates.

### P2 — Product research is not autonomous

Product name/details are caller-supplied. No product discovery, affiliate destination extraction, live product fact verification or price/availability validation is implemented in the reviewed baseline.

### P2 — Provider diagnostics can be billable

`POST /diagnostics/run` invokes Workers AI image generation and DeepSeek completion. It is not a cost-free read-only diagnostic even though it does not publish a Pin or persist a product.

### P2 — Parallel Pinterest write path

The service-key operation route exposes direct board/Pin creation outside publication ledger/idempotency/reconciliation. Restrict or remove these write operations, or bring them under the same durable state machine and audit trail.

### P3 — Legacy publication account attribution

Migration 007 adds nullable account_id; old rows may remain NULL and are omitted by account-filtered Learning Loop ingestion unless authoritatively backfilled.

### P3 — Image hosting assumption mismatch

The reviewed media implementation calls Cloudflare Workers AI and returns a Base64 data URL. It does not upload the generated image to Cloudflare Images or persist an image object.

## Test and workflow evidence limits

- The 119 individual test-function count is recorded in INDEX.md; this refresh did not execute pytest.
- Fake clients/cursors cannot prove PostgreSQL advisory-lock, transaction, pool recovery or concurrent refresh semantics.
- The opt-in PostgreSQL recovery test is destructive to a backend session and must only run against a disposable test database.
- CI workflows differ in Python version and PostgreSQL service availability. A green result must be tied to the exact workflow run and commit.
- GitHub combined status for audit commit `b11ab14...` returned no status entries, and commit-associated workflow-run lookup returned no runs. This is not evidence of a passing or failing CI run.

## Completion boundary

The source review and audit documentation are complete at module/function level for the recorded source baseline. This is not a claim that every nested helper method has an independent record, that every FN record is a statement-by-statement trace, or that the current Render deployment runs this source.

Runtime tests, production DB checks, provider calls, OAuth refresh, deployment and Pinterest publishing are not included. No real Pin was published. No production mutation or deployment is authorized by this audit.

## Required remediation order

1. Make authentication fail closed for every sensitive route, including the legacy direct-token route if retained.
2. Add per-account serialized refresh and wire expiry-aware refresh into publish and analytics flows.
3. Remove or govern direct Pinterest write operations outside the publication ledger.
4. Make board resolution paginated and avoid board side effects before workflow prerequisites.
5. Add durable operator reconciliation and alerting for unknown Pin outcomes.
6. Define the actual ML learning objective and evaluation loop; do not label analytics aggregation as ML.
7. Add product research/extraction with authoritative source validation if autonomous product selection is a requirement.
