# require_api_key — source-level review

- **ID:** `FN-APP-MAIN-PY-002`
- **Definition:** FastAPI dependency function
- **Source:** `app/main.py:44-51`
- **Source blob:** `37f5ccae0d171a8f8d6766cfb26013dbe221391c`
- **Baseline:** `336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Source review:** COMPLETE
- **Runtime verification:** NOT RUN

## Statement-level behavior

1. FastAPI injects the `X-API-Key` header as optional `x_api_key`; missing header becomes `None`.
2. The function reads the module-level `settings.app_api_key`.
3. If the configured key is falsy, it returns successfully. This is an intentional compatibility behavior but is fail-open: routes depending only on this dependency are unauthenticated when the secret is absent.
4. If a key is configured, a missing caller header or a value that fails `hmac.compare_digest` raises HTTP 401. Constant-time comparison is used for the comparison itself.
5. Successful validation returns `None`; FastAPI uses the dependency for gating, not as a credential-returning API.

## Callers and security impact

The dependency is attached to `/readiness`, `/diagnostics/providers`, product validation, product create/read, content generation and content history routes. In particular, `POST /products` writes to Neon and `POST /products/{product_id}/content` can call DeepSeek and write a content version. Those operations are exposed if `APP_API_KEY` is unset. Publish routes use the separate `require_configured_api_key` dependency and fail closed; diagnostics and learning routers have their own fail-closed dependencies.

## Tests and evidence

`tests/test_api.py::test_operational_routes_require_api_key_when_configured` checks rejection when a key is configured. `test_publish_routes_fail_closed_without_configured_api_key` checks publish-route fail-closed behavior. There is no demonstrated assertion that product-write/content-generation routes reject requests when `APP_API_KEY` is absent.

## Finding

**P1 — fail-open auth on routes using this dependency.** Replace the optional behavior with fail-closed behavior for all operational routes, or split public/read-only endpoints from protected operations explicitly. Add missing-key tests for product persistence and content generation. No code change was made during this audit.
