# Test helper and fixture audit — learning analytics

Source: `tests/test_learning.py`, baseline source SHA `d9e473659e348dd045cad60aa5524dd7a09f491c`.

The four module-level tests have separate TEST-LEARNING records. Nested support definitions:
- First `FakeConnection.__enter__/__exit__/execute` (lines 8–22) models successful DB context and captures the SELECT used to filter successful publications by account.
- Second `FakeConnection` (29–42) returns test publication rows and captures analytics snapshot INSERT statements/parameters.
- `FakeResponse.json` (43–52) returns the documented Pinterest analytics envelope.
- First `FakeClient.__init__/__enter__/__exit__/get` (54–75) captures GET URL, headers and params, and returns fake metrics response.
- `Conn` variants (82–92 and 121–132) capture database query/insert behavior for missing-metric and root-summary cases.
- `Response.json` variants (94–98 and 133–141) provide incomplete and top-level summary metrics respectively.
- `Client` variants (99–104 and 142–147) return the fake response without network access.

The tests exercise account filtering, supported Pinterest summary metric parsing, rejection/non-persistence of a requested metric absent from response, and root-level summary metrics with omitted zero metrics. Every DB and HTTP dependency is stubbed; this module does not prove live analytics ingestion or durable Neon writes.