"""Safe operator reconciliation tests; no live Pinterest writes are performed."""
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def auth(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    return {"X-API-Key": "test-api-key"}


def test_publication_status_endpoint_only_reads_database(monkeypatch):
    headers = auth(monkeypatch)
    calls = []
    row = {
        "id": 7, "status": "unknown", "board_id": "board-test",
        "created_at": None, "updated_at": None,
    }
    monkeypatch.setattr("app.database.get_publication", lambda publication_id: calls.append(publication_id) or row)
    response = client.get("/publications/7", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert calls == [7]


def test_reconcile_requires_authentication(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "test-api-key")
    response = client.post("/publications/7/reconcile", json={
        "outcome": "succeeded", "pinterest_pin_id": "pin-verified-1",
        "operator_evidence": "Confirmed in board list",
    })
    assert response.status_code == 401


def test_reconcile_success_requires_pin_id(monkeypatch):
    headers = auth(monkeypatch)
    response = client.post("/publications/7/reconcile", headers=headers, json={
        "outcome": "succeeded", "operator_evidence": "Confirmed in board list",
    })
    assert response.status_code == 422


def test_reconcile_failed_cannot_include_pin_id(monkeypatch):
    headers = auth(monkeypatch)
    response = client.post("/publications/7/reconcile", headers=headers, json={
        "outcome": "failed", "pinterest_pin_id": "pin-possibly-exists",
        "operator_evidence": "Checked all board listing pages",
    })
    assert response.status_code == 422


def test_reconcile_passes_operator_evidence_to_guarded_database_transition(monkeypatch):
    headers = auth(monkeypatch)
    calls = []
    row = {"id": 7, "status": "succeeded", "pinterest_pin_id": "pin-verified-1", "created_at": None, "updated_at": None}
    def reconcile(publication_id, **kwargs):
        calls.append((publication_id, kwargs))
        return row
    monkeypatch.setattr("app.database.reconcile_unknown_publication", reconcile)
    response = client.post("/publications/7/reconcile", headers=headers, json={
        "outcome": "succeeded", "pinterest_pin_id": "pin-verified-1",
        "operator_evidence": "Confirmed by read-only board listing",
    })
    assert response.status_code == 200
    assert response.json()["reconciled"] is True
    assert response.json()["published"] is True
    assert calls == [(7, {
        "outcome": "succeeded", "pinterest_pin_id": "pin-verified-1",
        "operator_evidence": "Confirmed by read-only board listing",
    })]


def test_reconcile_database_rejects_non_unknown_states(monkeypatch):
    import app.database as database
    class Cursor:
        def __init__(self): self.last = ""
        def execute(self, sql, params=None): self.last = " ".join(sql.split()); return self
        def fetchone(self):
            if "SELECT * FROM pin_publications" in self.last:
                return {"id": 7, "status": "succeeded", "pinterest_pin_id": "already-published"}
            return None
    class Context:
        def __enter__(self): return Cursor()
        def __exit__(self, *_): return False
    monkeypatch.setattr(database, "connection", lambda: Context())
    import pytest
    with pytest.raises(ValueError, match="only unknown"):
        database.reconcile_unknown_publication(7, outcome="failed", operator_evidence="Board checked, absent")


def test_reconcile_database_requires_verified_pin_id_for_success(monkeypatch):
    import pytest
    import app.database as database
    with pytest.raises(ValueError, match="Pin ID"):
        database.reconcile_unknown_publication(7, outcome="succeeded", operator_evidence="Board shows no matching Pin")


class StatefulPublicationHarness:
    """Small SQL-shape harness for exercising reconciliation + retry guard together."""
    def __init__(self, state="unknown"):
        self.row = {
            "id": 7, "product_id": 10, "content_version_id": 20,
            "board_id": "board-test", "account_id": "pinterest:test",
            "status": state, "attempt_count": 1, "pinterest_pin_id": None,
            "http_status": None, "error_code": "pinterest_outcome_uncertain",
            "response_metadata": {},
        }
        self.sql = ""
        self.params = ()
        self.calls = []

    def execute(self, sql, params=None):
        self.sql = " ".join(sql.split())
        self.params = tuple(params or ())
        self.calls.append((self.sql, self.params))
        return self

    def fetchone(self):
        if "SELECT * FROM pin_publications WHERE id = %s FOR UPDATE" in self.sql:
            return dict(self.row) if self.row else None
        if self.sql.startswith("UPDATE pin_publications"):
            if "SET status = 'succeeded'" in self.sql:
                pin_id, evidence, publication_id = self.params
                assert publication_id == self.row["id"]
                self.row.update(status="succeeded", pinterest_pin_id=pin_id, error_code=None)
            elif "SET status = 'failed'" in self.sql:
                evidence, publication_id = self.params
                assert publication_id == self.row["id"]
                self.row.update(status="failed", pinterest_pin_id=None, error_code="operator_verified_pin_absent")
            elif "SET status = 'pending'" in self.sql:
                account_id, publication_id = self.params
                assert publication_id == self.row["id"]
                self.row.update(status="pending", attempt_count=self.row["attempt_count"] + 1)
            return dict(self.row) if self.row else None
        if self.sql.startswith("SELECT * FROM pin_publications WHERE content_version_id"):
            return dict(self.row) if self.row else None
        if self.sql.startswith("INSERT INTO pin_publications"):
            self.row = {
                "id": 8, "product_id": self.params[0], "content_version_id": self.params[1],
                "board_id": self.params[2], "account_id": self.params[3],
                "status": "pending", "attempt_count": 1, "pinterest_pin_id": None,
            }
            return dict(self.row)
        return None


class StatefulConnectionContext:
    def __init__(self, harness):
        self.harness = harness
    def __enter__(self): return self.harness
    def __exit__(self, *_): return False


def test_stateful_reconcile_success_preserves_duplicate_publish_block(monkeypatch):
    import app.database as database
    harness = StatefulPublicationHarness("unknown")
    monkeypatch.setattr(database, "connection", lambda: StatefulConnectionContext(harness))

    saved = database.reconcile_unknown_publication(
        7, outcome="succeeded", pinterest_pin_id="pin-confirmed-123",
        operator_evidence="Read every board page and verified Pin detail endpoint",
    )
    assert saved["status"] == "succeeded"
    assert saved["pinterest_pin_id"] == "pin-confirmed-123"
    assert saved["error_code"] is None

    attempt = database.begin_publish_attempt(
        product_id=10, content_version_id=20, board_id="board-test", account_id="pinterest:test",
    )
    assert attempt["blocked"] is True
    assert attempt["status"] == "succeeded"
    assert harness.row["attempt_count"] == 1


def test_stateful_reconcile_verified_absence_enables_one_retry(monkeypatch):
    import app.database as database
    harness = StatefulPublicationHarness("unknown")
    monkeypatch.setattr(database, "connection", lambda: StatefulConnectionContext(harness))

    saved = database.reconcile_unknown_publication(
        7, outcome="failed", operator_evidence="All board pages loaded; no candidate Pin exists",
    )
    assert saved["status"] == "failed"
    assert saved["pinterest_pin_id"] is None
    assert saved["error_code"] == "operator_verified_pin_absent"

    attempt = database.begin_publish_attempt(
        product_id=10, content_version_id=20, board_id="board-test", account_id="pinterest:test",
    )
    assert attempt["blocked"] is False
    assert attempt["status"] == "pending"
    assert attempt["attempt_count"] == 2


def test_stateful_reconciliation_records_audit_metadata_and_rejects_second_transition(monkeypatch):
    import pytest
    import app.database as database
    harness = StatefulPublicationHarness("unknown")
    monkeypatch.setattr(database, "connection", lambda: StatefulConnectionContext(harness))

    database.reconcile_unknown_publication(
        7, outcome="succeeded", pinterest_pin_id="pin-confirmed-123",
        operator_evidence="All board pages and direct Pin response verified",
    )
    update_sql = [sql for sql, _ in harness.calls if sql.startswith("UPDATE pin_publications")]
    assert any("response_metadata = COALESCE(response_metadata" in sql for sql in update_sql)
    assert any("operator_board_verification" in sql for sql in update_sql)
    with pytest.raises(ValueError, match="only unknown"):
        database.reconcile_unknown_publication(
            7, outcome="failed", operator_evidence="Second transition must not be accepted",
        )


def test_stateful_unknown_state_still_blocks_retry_without_reconciliation(monkeypatch):
    import app.database as database
    harness = StatefulPublicationHarness("unknown")
    monkeypatch.setattr(database, "connection", lambda: StatefulConnectionContext(harness))
    attempt = database.begin_publish_attempt(
        product_id=10, content_version_id=20, board_id="board-test", account_id="pinterest:test",
    )
    assert attempt["blocked"] is True
    assert attempt["status"] == "unknown"
    assert harness.row["status"] == "unknown"
    assert not any(sql.startswith("UPDATE pin_publications") or sql.startswith("INSERT INTO pin_publications") for sql, _ in harness.calls)
