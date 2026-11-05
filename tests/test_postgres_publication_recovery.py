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



def test_workflow_idempotency_insert_is_race_safe_and_recovers_same_record(
    isolated_postgres,
):
    """Concurrent same-key workflow requests resolve to one product/content pair."""
    from concurrent.futures import ThreadPoolExecutor
    import threading

    key = f"pb-workflow-race-{uuid.uuid4().hex}"
    fingerprint = "same-request-fingerprint"
    barrier = threading.Barrier(8)

    def create_one(index):
        barrier.wait(timeout=10)
        return database.create_product_with_content_version(
            product_name="Concurrent workflow fixture",
            product_details="Same payload across concurrent workers",
            image_url=None,
            affiliate_url="https://example.invalid/concurrent-workflow",
            idempotency_key=key,
            request_fingerprint=fingerprint,
            provider="test-stub",
            model_id=f"worker-{index}",
            prompt_version="concurrency-test",
            pin_idea="fixture",
            title="fixture title",
            description="fixture description",
            alt_text="fixture alt",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create_one, range(8)))

    product_ids = {product["id"] for product, _ in results}
    content_ids = {content["id"] for _, content in results}
    assert len(product_ids) == 1
    assert len(content_ids) == 1
    with database.connection() as conn:
        product_count = conn.execute(
            "SELECT COUNT(*) AS n FROM products WHERE idempotency_key = %s", (key,)
        ).fetchone()["n"]
        content_count = conn.execute(
            "SELECT COUNT(*) AS n FROM content_versions WHERE product_id = %s",
            (next(iter(product_ids)),),
        ).fetchone()["n"]
    assert product_count == 1
    assert content_count == 1

    with pytest.raises(ValueError, match="idempotency_key_payload_mismatch"):
        database.create_product_with_content_version(
            product_name="Different payload", product_details="Different details",
            image_url=None, affiliate_url="https://example.invalid/other",
            idempotency_key=key, request_fingerprint="different-fingerprint",
            provider="test-stub", model_id="test", prompt_version="test",
            pin_idea="different", title="different", description="different", alt_text="different",
        )


def test_concurrent_publish_reservations_allow_exactly_one_provider_attempt(
    isolated_postgres,
):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    board_id = f"concurrent-board-{uuid.uuid4().hex}"
    barrier = threading.Barrier(8)

    def reserve(_index):
        barrier.wait(timeout=10)
        return database.begin_publish_attempt(
            product_id=product["id"], content_version_id=content["id"],
            board_id=board_id, account_id="test-account-never-used-for-API",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        attempts = list(pool.map(reserve, range(8)))
    assert sum(not attempt["blocked"] for attempt in attempts) == 1
    assert sum(attempt["blocked"] for attempt in attempts) == 7
    assert {attempt["id"] for attempt in attempts}.__len__() == 1
    assert {attempt["attempt_count"] for attempt in attempts} == {1}


def test_stale_pending_publication_can_be_operator_reconciled_after_board_verification(
    isolated_postgres,
):
    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    board_id = f"stale-pending-board-{uuid.uuid4().hex}"
    reserved = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"], board_id=board_id,
    )
    with database.connection() as conn:
        conn.execute(
            "UPDATE pin_publications SET updated_at = now() - interval '11 minutes' WHERE id = %s",
            (reserved["id"],),
        )

    reconciled = database.reconcile_unknown_publication(
        reserved["id"], outcome="failed",
        operator_evidence="CI disposable fixture: all board pages checked; provider stub confirms absence.",
    )
    assert reconciled["status"] == "failed"
    assert reconciled["error_code"] == "operator_verified_pin_absent"


def test_recent_pending_publication_cannot_be_operator_reconciled(
    isolated_postgres,
):
    product = isolated_postgres["product"]
    content = isolated_postgres["content"]
    reserved = database.begin_publish_attempt(
        product_id=product["id"], content_version_id=content["id"],
        board_id=f"recent-pending-board-{uuid.uuid4().hex}",
    )
    with pytest.raises(ValueError, match="at least 10 minutes old"):
        database.reconcile_unknown_publication(
            reserved["id"], outcome="failed",
            operator_evidence="CI fixture: deliberately too early to reconcile this pending row.",
        )


def test_workflow_generation_reservation_serializes_same_key(isolated_postgres):
    import concurrent.futures

    key = f"pb12-reserve-{uuid.uuid4().hex}"
    fingerprint = "a" * 64
    tokens = [str(uuid.uuid4()) for _ in range(8)]

    def reserve(token):
        return database.reserve_workflow_generation(
            idempotency_key=key, request_fingerprint=fingerprint,
            lease_token=token, lease_seconds=600,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, tokens))
    assert sum(bool(item["acquired"]) for item in results) == 1
    assert sum(item["status"] == "generating" for item in results) == 8
    with database.connection() as conn:
        row = conn.execute(
            "SELECT count(*) AS count FROM workflow_generation_reservations WHERE idempotency_key = %s",
            (key,),
        ).fetchone()
    assert row["count"] == 1
    with pytest.raises(ValueError, match="idempotency_key_payload_mismatch"):
        database.reserve_workflow_generation(
            idempotency_key=key, request_fingerprint="b" * 64,
            lease_token=str(uuid.uuid4()),
        )
    with database.connection() as conn:
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))


def test_workflow_generation_checkpoints_survive_retryable_failure(isolated_postgres):
    key = f"pb12-cache-{uuid.uuid4().hex}"
    fingerprint = "c" * 64
    first_token = str(uuid.uuid4())
    first = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint, lease_token=first_token,
    )
    assert first["acquired"] is True
    database.save_workflow_generation_image(
        idempotency_key=key, lease_token=first_token,
        image_data_url="data:image/png;base64,ZmFrZQ==", image_model="test-image",
    )
    database.release_workflow_generation(idempotency_key=key, lease_token=first_token)

    second_token = str(uuid.uuid4())
    second = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint, lease_token=second_token,
    )
    assert second["acquired"] is True
    assert second["image_data_url"] == "data:image/png;base64,ZmFrZQ=="
    assert second["image_model"] == "test-image"
    database.save_workflow_generation_content(
        idempotency_key=key, lease_token=second_token,
        generated_content={"title": "test", "description": "test", "alt_text": "test", "pin_idea": "test"},
        content_model="test-content",
    )
    database.release_workflow_generation(idempotency_key=key, lease_token=second_token)
    third_token = str(uuid.uuid4())
    third = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint, lease_token=third_token,
    )
    assert third["acquired"] is True
    assert third["image_data_url"] == "data:image/png;base64,ZmFrZQ=="
    assert third["generated_content"]["title"] == "test"
    database.release_workflow_generation(idempotency_key=key, lease_token=third_token)
    with database.connection() as conn:
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))


def test_expired_generation_lease_cannot_checkpoint_or_finalize(isolated_postgres):
    key = f"pb12-expired-lease-{uuid.uuid4().hex}"
    fingerprint = "f" * 64
    lease_token = str(uuid.uuid4())
    reservation = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint,
        lease_token=lease_token, lease_seconds=600,
    )
    assert reservation["acquired"] is True
    with database.connection() as conn:
        conn.execute(
            "UPDATE workflow_generation_reservations SET lease_expires_at = now() - interval '1 second' "
            "WHERE idempotency_key = %s", (key,),
        )

    with pytest.raises(RuntimeError, match="lease lost before image checkpoint"):
        database.save_workflow_generation_image(
            idempotency_key=key, lease_token=lease_token,
            image_data_url="data:image/png;base64,ZmFrZQ==", image_model="expired-test-image",
        )
    with pytest.raises(RuntimeError, match="lease lost before content checkpoint"):
        database.save_workflow_generation_content(
            idempotency_key=key, lease_token=lease_token,
            generated_content={"pin_idea": "test", "title": "test", "description": "test", "alt_text": "test"},
            content_model="expired-test-content",
        )
    with pytest.raises(RuntimeError, match="lease lost before atomic product/content completion"):
        database.create_product_with_content_version(
            product_name="Expired lease fixture", product_details="Test only", image_url=None,
            affiliate_url="https://example.invalid/expired", idempotency_key=key,
            request_fingerprint=fingerprint, lease_token=lease_token, provider="test",
            model_id="expired-test-content", prompt_version="test", pin_idea="test",
            title="test", description="test", alt_text="test",
        )
    with database.connection() as conn:
        product_count = conn.execute(
            "SELECT count(*) AS n FROM products WHERE idempotency_key = %s", (key,),
        ).fetchone()["n"]
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))
    assert product_count == 0


def test_product_content_and_generation_completion_are_one_transaction(isolated_postgres):
    key = f"pb12-atomic-complete-{uuid.uuid4().hex}"
    fingerprint = "d" * 64
    lease_token = str(uuid.uuid4())
    reservation = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint, lease_token=lease_token,
    )
    assert reservation["acquired"] is True
    database.save_workflow_generation_image(
        idempotency_key=key, lease_token=lease_token,
        image_data_url="data:image/png;base64,ZmFrZQ==", image_model="atomic-test-image",
    )
    database.save_workflow_generation_content(
        idempotency_key=key, lease_token=lease_token,
        generated_content={"pin_idea": "test", "title": "test", "description": "test", "alt_text": "test"},
        content_model="atomic-test-content",
    )

    product, content = database.create_product_with_content_version(
        product_name="Atomic completion fixture", product_details="Test only", image_url=None,
        affiliate_url="https://example.invalid/atomic", idempotency_key=key,
        request_fingerprint=fingerprint, lease_token=lease_token, provider="test",
        model_id="atomic-test-content", prompt_version="test", pin_idea="test",
        title="test", description="test", alt_text="test",
    )

    with database.connection() as conn:
        row = conn.execute(
            "SELECT status, product_id, image_data_url, generated_content, lease_token "
            "FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,),
        ).fetchone()
    assert row["status"] == "persisted"
    assert row["product_id"] == product["id"]
    assert row["image_data_url"] is None
    assert row["generated_content"] is None
    assert row["lease_token"] is None
    assert content["product_id"] == product["id"]
    with database.connection() as conn:
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))
        conn.execute("DELETE FROM products WHERE id = %s", (product["id"],))


def test_lost_generation_lease_rolls_back_product_and_content_transaction(isolated_postgres):
    key = f"pb12-lost-lease-{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError, match="lease lost before atomic product/content completion"):
        database.create_product_with_content_version(
            product_name="Must roll back", product_details="Test only", image_url=None,
            affiliate_url="https://example.invalid/rollback", idempotency_key=key,
            request_fingerprint="e" * 64, lease_token=str(uuid.uuid4()), provider="test",
            model_id="test", prompt_version="test", pin_idea="test", title="test",
            description="test", alt_text="test",
        )
    with database.connection() as conn:
        product_count = conn.execute(
            "SELECT count(*) AS n FROM products WHERE idempotency_key = %s", (key,),
        ).fetchone()["n"]
    assert product_count == 0


def test_expired_generation_lease_is_reclaimed_after_row_lock_wait(isolated_postgres):
    """Lease decisions use wall-clock time after a transaction waits on a row lock."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    import time

    key = f"pb12-lock-wait-{uuid.uuid4().hex}"
    fingerprint = "d" * 64
    old_token = str(uuid.uuid4())
    new_token = str(uuid.uuid4())
    first = database.reserve_workflow_generation(
        idempotency_key=key,
        request_fingerprint=fingerprint,
        lease_token=old_token,
        lease_seconds=2,
    )
    assert first["acquired"] is True

    lock_acquired = threading.Event()
    release_lock = threading.Event()
    reclaim_started = threading.Event()

    def hold_row_lock():
        with database.connection() as conn:
            conn.execute(
                "SELECT idempotency_key FROM workflow_generation_reservations "
                "WHERE idempotency_key = %s FOR UPDATE",
                (key,),
            )
            lock_acquired.set()
            assert release_lock.wait(timeout=10), "test did not release the reservation row lock"

    def reclaim_after_wait():
        reclaim_started.set()
        return database.reserve_workflow_generation(
            idempotency_key=key,
            request_fingerprint=fingerprint,
            lease_token=new_token,
            lease_seconds=30,
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            lock_future = executor.submit(hold_row_lock)
            assert lock_acquired.wait(timeout=5), "could not acquire reservation row lock"

            reclaim_future = executor.submit(reclaim_after_wait)
            assert reclaim_started.wait(timeout=5), "reclaim worker did not start"

            # Confirm the second transaction is actually waiting on the row lock.
            deadline = time.monotonic() + 5
            waiting = False
            while time.monotonic() < deadline:
                with database.connection() as conn:
                    waiting = conn.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                              AND wait_event_type = 'Lock'
                              AND query LIKE 'SELECT * FROM workflow_generation_reservations%'
                        ) AS waiting
                        """
                    ).fetchone()["waiting"]
                if waiting:
                    break
                time.sleep(0.05)
            assert waiting, "reclaim transaction never entered a PostgreSQL row-lock wait"

            # The transaction began before expiry; the lease expires while it is blocked.
            time.sleep(2.1)
            release_lock.set()
            lock_future.result(timeout=5)
            reclaimed = reclaim_future.result(timeout=10)

        assert reclaimed["acquired"] is True
        assert str(reclaimed["lease_token"]) == new_token
        assert reclaimed["lease_expires_at"] is not None
    finally:
        release_lock.set()
        with database.connection() as conn:
            conn.execute(
                "DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s",
                (key,),
            )


def test_expired_workflow_checkpoints_are_cleared_but_idempotency_tombstones_remain(isolated_postgres):
    key = f"pb12-retention-{uuid.uuid4().hex}"
    fingerprint = "9" * 64
    token = str(uuid.uuid4())
    reservation = database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint=fingerprint, lease_token=token,
    )
    assert reservation["acquired"] is True
    database.save_workflow_generation_image(
        idempotency_key=key, lease_token=token,
        image_data_url="data:image/png;base64,ZmFrZQ==", image_model="retention-test-image",
    )
    database.save_workflow_generation_content(
        idempotency_key=key, lease_token=token,
        generated_content={"pin_idea": "temporary", "title": "temporary", "description": "temporary", "alt_text": "temporary"},
        content_model="retention-test-content",
    )
    database.release_workflow_generation(idempotency_key=key, lease_token=token)

    with database.connection() as conn:
        conn.execute(
            "UPDATE workflow_generation_reservations SET updated_at = clock_timestamp() - interval '73 hours' "
            "WHERE idempotency_key = %s", (key,),
        )

    cleared = database.cleanup_expired_workflow_checkpoints(retention_hours=72)
    assert cleared >= 1
    with database.connection() as conn:
        row = conn.execute(
            "SELECT request_fingerprint, status, image_data_url, image_model, generated_content, content_model "
            "FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,),
        ).fetchone()
    assert row["request_fingerprint"] == fingerprint
    assert row["status"] == "retryable"
    assert row["image_data_url"] is None
    assert row["image_model"] is None
    assert row["generated_content"] is None
    assert row["content_model"] is None

    # The original key/fingerprint remains reserved after payload expiry.
    with pytest.raises(ValueError, match="idempotency_key_payload_mismatch"):
        database.reserve_workflow_generation(
            idempotency_key=key, request_fingerprint="8" * 64,
            lease_token=str(uuid.uuid4()),
        )
    with database.connection() as conn:
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))


def test_checkpoint_cleanup_does_not_clear_a_live_generation_lease(isolated_postgres):
    key = f"pb12-retention-live-{uuid.uuid4().hex}"
    token = str(uuid.uuid4())
    database.reserve_workflow_generation(
        idempotency_key=key, request_fingerprint="7" * 64, lease_token=token,
    )
    database.save_workflow_generation_image(
        idempotency_key=key, lease_token=token,
        image_data_url="data:image/png;base64,ZmFrZQ==", image_model="live-test-image",
    )
    with database.connection() as conn:
        conn.execute(
            "UPDATE workflow_generation_reservations SET updated_at = clock_timestamp() - interval '73 hours' "
            "WHERE idempotency_key = %s", (key,),
        )
    database.cleanup_expired_workflow_checkpoints(retention_hours=72)
    with database.connection() as conn:
        row = conn.execute(
            "SELECT status, image_data_url FROM workflow_generation_reservations WHERE idempotency_key = %s",
            (key,),
        ).fetchone()
    assert row["status"] == "generating"
    assert row["image_data_url"] == "data:image/png;base64,ZmFrZQ=="
    database.release_workflow_generation(idempotency_key=key, lease_token=token)
    with database.connection() as conn:
        conn.execute("DELETE FROM workflow_generation_reservations WHERE idempotency_key = %s", (key,))
