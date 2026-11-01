# Test helper audit — database pool

Source: `tests/test_database_pool_recovery.py` (118 lines), exact source retrieved from main.

- `restore_pool(monkeypatch)` (fixture, lines 12–22): snapshots the module-global pool, clears it for test isolation, yields, closes a newly created pool best-effort, then restores the original global. The broad cleanup exception is deliberately swallowed so teardown does not mask the test result; it can also conceal a close failure.
- `FakePool.__init__(**kwargs)` (nested, lines 39–41): stores constructor arguments and records instances for lazy-singleton assertions.
- `FakePool.close()` (nested, lines 43–44): no-op close stub.
- `FakeLease.__enter__()` / `__exit__(exc_type, exc, tb)` (nested, lines 81–86): model pool checkout context entry/exit and capture whether an exception crossed the context boundary.
- First nested `FakePool.connection()` (lines 88–91): records checkout and returns the lease stub.
- `BrokenLease.__enter__()` / `__exit__(*args)` (nested, lines 103–107): raises a simulated stale-lease connection error; exit returns false so exceptions are not suppressed.
- Second nested `FakePool.connection()` (lines 109–111): returns the broken lease.

The six module-level tests cover missing configuration, lazy singleton construction and constructor options, close/reset behavior, safe close when absent, connection-context delegation and propagation of checkout errors. All pool objects are fakes; no PostgreSQL connection or recovery is proven by this module.