"""Product/content and publication reservation must commit as one transaction."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import database


def _arguments():
    return {
        "product_name": "Three-tier spice rack",
        "product_details": "A kitchen organizer.",
        "image_url": None,
        "affiliate_url": "https://example.com/affiliate?tag=home-20",
        "idempotency_key": "atomic-publish-key-123",
        "provider": "deepseek",
        "model_id": "test-model",
        "prompt_version": "test-v1",
        "pin_idea": "Organize spices",
        "title": "Spice rack organization",
        "description": "Keep spices tidy.",
        "alt_text": "A spice rack on a counter.",
        "publication_board_id": "board-1",
        "publication_account_id": "pinterest:account-1",
    }


class FakeConnection:
    def __init__(self, *, fail_publication=False):
        self.fail_publication = fail_publication
        self.statements = []

    def execute(self, sql, params):
        self.statements.append((sql, params))
        if "INSERT INTO products" in sql:
            row = {"id": 10, "product_name": params[0], "idempotency_key": params[4]}
        elif "INSERT INTO content_versions" in sql:
            row = {"id": 20, "product_id": params[0], "title": params[5]}
        elif "INSERT INTO pin_publications" in sql:
            if self.fail_publication:
                raise RuntimeError("publication reservation insert failed")
            row = {"id": 30, "product_id": params[0], "content_version_id": params[1], "board_id": params[2], "account_id": params[3], "status": "pending"}
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")
        return SimpleNamespace(fetchone=lambda: row)


def test_product_content_and_publication_reservation_share_one_transaction(monkeypatch):
    conn = FakeConnection()
    state = {"commits": 0, "rollbacks": 0}

    @contextmanager
    def fake_connection():
        try:
            yield conn
        except Exception:
            state["rollbacks"] += 1
            raise
        else:
            state["commits"] += 1

    monkeypatch.setattr(database, "connection", fake_connection)
    product, content, publication = database.create_product_with_content_version(**_arguments())

    assert product["id"] == 10
    assert content["id"] == 20
    assert publication["id"] == 30
    assert publication["account_id"] == "pinterest:account-1"
    assert publication["status"] == "pending"
    assert len(conn.statements) == 3
    assert state == {"commits": 1, "rollbacks": 0}


def test_publication_reservation_failure_rolls_back_product_and_content(monkeypatch):
    conn = FakeConnection(fail_publication=True)
    state = {"commits": 0, "rollbacks": 0}

    @contextmanager
    def fake_connection():
        try:
            yield conn
        except Exception:
            state["rollbacks"] += 1
            raise
        else:
            state["commits"] += 1

    monkeypatch.setattr(database, "connection", fake_connection)

    with pytest.raises(RuntimeError, match="reservation insert failed"):
        database.create_product_with_content_version(**_arguments())

    assert len(conn.statements) == 3
    assert state == {"commits": 0, "rollbacks": 1}
