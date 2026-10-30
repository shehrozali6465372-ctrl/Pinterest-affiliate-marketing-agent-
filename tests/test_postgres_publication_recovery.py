"""Real PostgreSQL integration checks for uncertain Pinterest publication recovery.

Runs only when TEST_DATABASE_URL points to a dedicated, disposable PostgreSQL database.
Never uses DATABASE_URL and never calls Pinterest.
"""
from __future__ import annotations

import os
import uuid

import pytest

from app import database


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is set only for isolated PostgreSQL CI integration tests",
)


@pytest.fixture
def isolated_postgres(monkeypatch):
    """Apply migrations to the CI-only database and cleanup only this test's rows."""
    assert TEST_DATABASE_URL, "fixture must never silently use DATABASE_URL"
    monkeypatch.setattr(database.settings, "database_url", TEST_DATABASE_URL)
    database.close_pool()
    monkeypatch.setattr(database, "_pool", None)
    database.run_migrations()
    suffix = uuid.uuid4().hex
    product = database.create_product(
        product_name=f"PB07 integration {suffix}",
        product_details="Disposable integration fixture; no live product or image.",
        image_url=None,
        affiliate_url="https://example.invalid/affiliate-test",
        idempotency_key=f"pb07-test-{suffix}",
    )
    content = database.create_content_version(
        product_id=product["id"],
        provider="test-stub",
        model_id="integration-test",
        prompt_version="pb07-test",
        pin_idea="fixture only",
        title="fixture only",
        description="fixture only",
        alt_text="fixture only",
    )
    try:
        yield {"product": product, "content": content}
    finally:
        with database.connection() as conn:
            conn.execute("DELETE FROM products WHERE id = %s", (product["id"],))
        database.close_pool()


def test_unknown_publication_reconciliation_is_durable_and_blocks_duplicate_publish(
    isolated_postgres,
):
    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    board_id = f"test-board-{uuid.uuid4().hex}"

    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id="test-account-never-used-for-API",
    )
    assert reserved["blocked"] is False

    marked_unknown = database.finish_publish_attempt(
        reserved["id"], status="unknown", http_status=None,
        error_code="simulated_timeout", response_metadata={"source": "ci-test-stub"},
    )
    assert marked_unknown["status"] == "unknown"

    # The reservation guard must block a retry before any publisher is called.
    blocked = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id="test-account-never-used-for-API",
    )
    assert blocked["blocked"] is True
    assert blocked["status"] == "unknown"
    assert blocked["attempt_count"] == 1

    pin_id = f"test-pin-{uuid.uuid4().hex}"
    reconciled = database.reconcile_unknown_publication(
        reserved["id"],
        outcome="succeeded",
        pinterest_pin_id=pin_id,
        operator_evidence="CI fixture: provider state stub confirms this test Pin ID.",
    )
    assert reconciled["status"] == "succeeded"
    assert reconciled["pinterest_pin_id"] == pin_id
    assert reconciled["response_metadata"]["reconciliation"]["method"] == "operator_board_verification"

    # Verify persistence via a fresh connection, then verify duplicate retries remain blocked.
    with database.connection() as conn:
        durable = conn.execute(
            "SELECT status, pinterest_pin_id, attempt_count, response_metadata "
            "FROM pin_publications WHERE id = %s",
            (reserved["id"],),
        ).fetchone()
    assert durable["status"] == "succeeded"
    assert durable["pinterest_pin_id"] == pin_id
    assert durable["attempt_count"] == 1
    assert durable["response_metadata"]["reconciliation"]["evidence"].startswith("CI fixture:")

    second_retry = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id="test-account-never-used-for-API",
    )
    assert second_retry["blocked"] is True
    assert second_retry["status"] == "succeeded"
    assert second_retry["attempt_count"] == 1


def test_unknown_publication_is_not_retryable_until_explicit_absence_reconciliation(
    isolated_postgres,
):
    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    board_id = f"test-board-{uuid.uuid4().hex}"
    reserved = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"], board_id=board_id,
    )
    database.finish_publish_attempt(
        reserved["id"], status="unknown", error_code="simulated_timeout",
    )

    blocked = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"], board_id=board_id,
    )
    assert blocked["blocked"] is True

    failed = database.reconcile_unknown_publication(
        reserved["id"], outcome="failed",
        operator_evidence="CI fixture: isolated provider stub confirms no Pin exists.",
    )
    assert failed["status"] == "failed"
    assert failed["error_code"] == "operator_verified_pin_absent"

    retry = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"], board_id=board_id,
    )
    assert retry["blocked"] is False
    assert retry["status"] == "pending"
    assert retry["attempt_count"] == 2


def test_migrations_are_idempotent_on_postgres(isolated_postgres):
    # The fixture already ran migrations; a second pass must succeed without DDL errors.
    database.run_migrations()
    with database.connection() as conn:
        versions = conn.execute("SELECT COUNT(*) AS total FROM schema_migrations").fetchone()["total"]
    assert versions >= 8


def test_operator_http_reconciliation_round_trip_on_disposable_postgres(
    isolated_postgres, monkeypatch,
):
    """Exercise the authenticated API + real disposable DB; Pinterest remains stubbed out."""
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "app_api_key", "pb07-integration-only-key")
    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    board_id = f"test-board-{uuid.uuid4().hex}"
    reserved = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"],
        board_id=board_id, account_id="test-account-never-used-for-API",
    )
    database.finish_publish_attempt(
        reserved["id"], status="unknown", error_code="simulated_timeout",
        response_metadata={"source": "disposable-postgres-provider-stub"},
    )

    with TestClient(app) as client:
        # Both operator endpoints must fail closed without the configured API key.
        assert client.get(f"/publications/{reserved['id']}").status_code == 401
        assert client.post(
            f"/publications/{reserved['id']}/reconcile",
            json={"outcome": "succeeded", "pinterest_pin_id": "stub-pin-verified",
                  "operator_evidence": "Disposable provider stub confirms this Pin exists"},
        ).status_code == 401

        headers = {"X-API-Key": "pb07-integration-only-key"}
        before = client.get(f"/publications/{reserved['id']}", headers=headers)
        assert before.status_code == 200
        assert before.json()["status"] == "unknown"

        blocked = database.begin_publish_attempt(
            product_id=product["id"], content_version_id=content["id"],
            board_id=board_id, account_id="test-account-never-used-for-API",
        )
        assert blocked["blocked"] is True
        assert blocked["status"] == "unknown"

        reconciled = client.post(
            f"/publications/{reserved['id']}/reconcile", headers=headers,
            json={"outcome": "succeeded", "pinterest_pin_id": "stub-pin-verified",
                  "operator_evidence": "Disposable provider stub confirms this Pin exists"},
        )
        assert reconciled.status_code == 200
        assert reconciled.json()["publication"]["status"] == "succeeded"

        after = client.get(f"/publications/{reserved['id']}", headers=headers)
        assert after.status_code == 200
        assert after.json()["status"] == "succeeded"
        assert after.json()["pinterest_pin_id"] == "stub-pin-verified"
        assert after.json()["response_metadata"]["reconciliation"]["method"] == "operator_board_verification"

    retry = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"],
        board_id=board_id, account_id="test-account-never-used-for-API",
    )
    assert retry["blocked"] is True
    assert retry["status"] == "succeeded"
    assert retry["attempt_count"] == 1
