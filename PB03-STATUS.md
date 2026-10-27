# PB-03 / PB-01 / PB-05 / PB-06 / PB-07 release status

**Current status: merged and deployed on 2026-10-27; real OAuth handoff and production analytics snapshot remain open verification gates.**

## Release evidence

- Agent PR #21: https://github.com/shehrozali6465372-ctrl/Pinterest-affiliate-marketing-agent-/pull/21 — merged as `ed56c0300922684ed4d2ca65f80d76dcdd4fe63f`.
- GitHub Actions on the merged main SHA: Python CI **PASS**; Python tests on the PR head **PASS**. Local integrated test suite: **65 passed, 1 Starlette/httpx TestClient deprecation warning**. Compile and `git diff --check` passed.
- Render Agent deployment `dep-dbg5sasipgvc73ek69c0`: **live**, SHA `ed56c0300922684ed4d2ca65f80d76dcdd4fe63f`.
- Public `GET /health`: HTTP 200. Anonymous `GET /readiness`: HTTP 401, expected because this diagnostic endpoint requires `X-API-Key`.
- Code includes PB-01 idempotency recovery, PB-03 separation of legacy/direct-token and stored-OAuth readiness, PB-05 refresh-expiry guards, PB-06 fail-closed metric validation, and PB-07 regression coverage for persistence/publish uncertainty.
- PB-01 PR #15 was closed as superseded by PR #21; its board-before-persistence behavior and recovery cases are in the deployed main branch.
- No new Pinterest Pin was created by the release or deployment verification.

## Production data check

Read-only Neon query against `pinterest_affiliate` found:
- Confirmed published Pin rows: **1**
- Connected Pinterest credential rows: **1**
- `pin_analytics_snapshots` rows: **0**

Therefore the real production analytics snapshot is **not yet verified**. This does not imply the analytics code is unimplemented; it means no live snapshot has been persisted/confirmed yet.

## Remaining human / production gates

1. **PB-04 real OAuth:** Hub PR #6 is merged and the backend is deployed. A human still needs to open `https://modern-living-hub.onrender.com/auth/pinterest`, sign in to Pinterest, and grant the requested access. After the callback, verify Hub confirms `stored === true`, Agent encrypted Neon storage, and account lookup. Do not paste tokens into chat.
2. **PB-06 live snapshot:** `/learning-loop/run` is protected by `X-API-Key`. The key is not present in the currently connected Debian shell, and the older device that previously held the authenticated safe diagnostics setup is offline. Reconnect that device or restore authorized local secret access; never expose the key in chat. Then run the protected analytics request only after checking eligible Pinterest metrics and verify the resulting Neon row.
3. **PB-05 refresh:** Automated tests cover expiry, rotation, and preservation when Pinterest omits a rotated refresh token. A live refresh was not forced because stored credentials are not near expiry.
4. **PB-07:** Fault and ambiguous-publish recovery have automated coverage. No fault injection was run against production because it could disrupt the service.

No credentials, token values, API keys, encryption keys, or ingest secrets are stored in this status file.
