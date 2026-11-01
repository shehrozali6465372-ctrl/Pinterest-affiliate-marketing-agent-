# Test helper audit — read-only Pinterest pagination

Source: `tests/test_pinterest_readonly.py`, SHA `899aeef79caf5b98acc6a3d9405f1da5c1d461f9`.

- `FakeResponse.__init__(body, status_code)` stores a body/status; `json()` returns the body.
- `FakeClient.__init__(responses)` stores ordered responses; `__enter__/__exit__` implement context management; `get(url, **kwargs)` records GET calls and returns the next fake response.
- `patch_client(monkeypatch, fake)` replaces the Pinterest module's httpx client with the fake.

Five separately recorded tests verify pagination through all bookmarks using GET only, fail-closed behavior for repeated bookmark, incomplete status at page cap, provider-error body sanitization, and Pin detail GET. No live Pinterest API call is made; pagination/contract assertions are against synthetic responses.