"""Deterministic state-machine tests for the publication guard without Pinterest calls."""

from app.database import begin_publish_attempt


class FakeCursor:
    def __init__(self, state=None):
        self.state = state
        self.last_sql = ""
        self.calls = []

    def execute(self, sql, params=None):
        self.last_sql = " ".join(sql.split())
        self.calls.append((self.last_sql, params))
        return self

    def fetchone(self):
        if "SELECT * FROM pin_publications" in self.last_sql:
            if self.state is None:
                return None
            return {"id": 55, "product_id": 10, "content_version_id": 20, "board_id": "board-test", "status": self.state, "attempt_count": 1, "pinterest_pin_id": None}
        if "UPDATE pin_publications" in self.last_sql:
            return {"id": 55, "product_id": 10, "content_version_id": 20, "board_id": "board-test", "status": "pending", "attempt_count": 2}
        if "INSERT INTO pin_publications" in self.last_sql:
            return {"id": 56, "product_id": 10, "content_version_id": 20, "board_id": "board-test", "status": "pending", "attempt_count": 1}
        return None


class FakeConnectionContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *_):
        return False


def run_with_state(monkeypatch, state):
    import app.database as database
    cursor = FakeCursor(state=state)
    monkeypatch.setattr(database, "connection", lambda: FakeConnectionContext(cursor))
    result = begin_publish_attempt(product_id=10, content_version_id=20, board_id="board-test", account_id="pinterest:test")
    return result, cursor


def test_unknown_publication_blocks_retry_without_state_mutation(monkeypatch):
    result, cursor = run_with_state(monkeypatch, "unknown")
    assert result["blocked"] is True
    assert result["status"] == "unknown"
    assert not any(sql.startswith("UPDATE pin_publications") or sql.startswith("INSERT INTO pin_publications") for sql, _ in cursor.calls)


def test_pending_publication_blocks_concurrent_retry(monkeypatch):
    result, cursor = run_with_state(monkeypatch, "pending")
    assert result["blocked"] is True
    assert result["status"] == "pending"
    assert not any(sql.startswith("UPDATE pin_publications") or sql.startswith("INSERT INTO pin_publications") for sql, _ in cursor.calls)


def test_succeeded_publication_blocks_duplicate_retry(monkeypatch):
    result, cursor = run_with_state(monkeypatch, "succeeded")
    assert result["blocked"] is True
    assert result["status"] == "succeeded"
    assert not any(sql.startswith("UPDATE pin_publications") or sql.startswith("INSERT INTO pin_publications") for sql, _ in cursor.calls)


def test_failed_publication_can_reserve_one_retry(monkeypatch):
    result, cursor = run_with_state(monkeypatch, "failed")
    assert result["blocked"] is False
    assert result["status"] == "pending"
    assert any(sql.startswith("UPDATE pin_publications") for sql, _ in cursor.calls)
