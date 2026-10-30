"""Unit coverage for lazy database-pool lifecycle and stale checkout checks."""

from types import SimpleNamespace

import pytest

from app import database
from app.config import settings


@pytest.fixture(autouse=True)
def restore_pool(monkeypatch):
    previous_pool = database._pool
    database._pool = None
    yield
    current_pool = database._pool
    if current_pool is not None and current_pool is not previous_pool:
        try:
            current_pool.close()
        except Exception:
            pass
    database._pool = previous_pool


def test_get_pool_requires_database_url_without_creating_pool(monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(database.DatabaseConfigurationError):
        database.get_pool()
    assert database._pool is None


def test_get_pool_creates_a_single_lazy_pool_with_stale_connection_check(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://unit.test/db")
    created = []

    class FakePool:
        check_connection = staticmethod(lambda connection: None)

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

        def close(self):
            pass

    monkeypatch.setattr(database, "ConnectionPool", FakePool)
    first = database.get_pool()
    second = database.get_pool()

    assert first is second
    assert len(created) == 1
    assert first.kwargs["conninfo"] == "postgresql://unit.test/db"
    assert first.kwargs["min_size"] == 1
    assert first.kwargs["max_size"] == 5
    assert first.kwargs["check"] is FakePool.check_connection
    assert first.kwargs["open"] is True


def test_close_pool_closes_and_resets_global_pool(monkeypatch):
    calls = []
    fake_pool = SimpleNamespace(close=lambda: calls.append("closed"))
    monkeypatch.setattr(database, "_pool", fake_pool)

    database.close_pool()

    assert calls == ["closed"]
    assert database._pool is None


def test_close_pool_is_safe_when_pool_was_never_created():
    assert database._pool is None
    database.close_pool()
    assert database._pool is None


def test_checkout_connection_context_uses_pool_connection_context(monkeypatch):
    """The public connection helper must delegate each checkout to the pool."""
    events = []

    class FakeLease:
        def __enter__(self):
            events.append("lease-enter")
            return "fake-connection"
        def __exit__(self, exc_type, exc, tb):
            events.append(("lease-exit", exc_type))
            return False

    class FakePool:
        def connection(self):
            events.append("checkout")
            return FakeLease()

    monkeypatch.setattr(settings, "database_url", "postgresql://unit.test/db")
    monkeypatch.setattr(database, "_pool", FakePool())
    with database.connection() as conn:
        assert conn == "fake-connection"
        events.append("query-scope")

    assert events == ["checkout", "lease-enter", "query-scope", ("lease-exit", None)]


def test_checkout_connection_context_returns_connection_errors_to_caller(monkeypatch):
    class BrokenLease:
        def __enter__(self):
            raise ConnectionError("simulated stale lease")
        def __exit__(self, *_):
            return False

    class FakePool:
        def connection(self):
            return BrokenLease()

    monkeypatch.setattr(settings, "database_url", "postgresql://unit.test/db")
    monkeypatch.setattr(database, "_pool", FakePool())
    with pytest.raises(ConnectionError, match="simulated stale lease"):
        with database.connection():
            pass
