# Test helper audit — publication state-machine fakes

Source: `tests/test_publish_recovery_state_machine.py`, SHA `2adffa42ccfc70f9e08c7ba8c329f0c64a59962f`.

- `FakeCursor.__init__(state)` stores a publication state; `execute(sql, params)` records the SQL/parameters; `fetchone()` returns a row shaped for the state transition under test.
- `FakeConnectionContext.__init__(cursor)` stores the cursor; `__enter__` returns it; `__exit__` does not suppress exceptions.
- `run_with_state(monkeypatch, state)` patches database connection to the fake context and invokes the reservation logic under a supplied state.

Four TEST-PUBLISH-STATE records cover unknown, pending, succeeded and failed states. These are unit-level state-machine checks; fake cursor does not model actual transaction isolation, row locks or concurrent PostgreSQL workers.