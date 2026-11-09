"""Disposable-PostgreSQL tests for the additive Model 2 registry migration."""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import database
from app.model2_domain import AccountNicheAssignmentInput, AccountProfileInput, NicheInput
from app.model2_learning import create_learning_snapshot, list_learning_snapshots
from app.model2_repository import (
    Model2AccountNotConnectedError,
    Model2ConflictError,
    Model2NotFoundError,
    create_niche,
    get_active_account_niche_context,
    list_account_niche_assignments,
    save_account_niche_assignment,
    save_account_profile,
    update_niche,
)
from psycopg.errors import CheckViolation, ForeignKeyViolation, RaiseException, SerializationFailure, UniqueViolation


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is reserved for isolated PostgreSQL CI",
)


@pytest.fixture()
def model2_db(monkeypatch):
    assert TEST_DATABASE_URL, "must never fall back to DATABASE_URL"
    monkeypatch.setattr(database.settings, "database_url", TEST_DATABASE_URL)
    database.close_pool()
    database.run_migrations()
    suffix = uuid4().hex[:12]
    account_a = f"pinterest:test-model2-a-{suffix}"
    account_b = f"pinterest:test-model2-b-{suffix}"
    account_c = f"pinterest:test-model2-c-{suffix}"
    niche_a = f"test-niche-a-{suffix}"
    niche_b = f"test-niche-b-{suffix}"
    try:
        with database.connection() as conn:
            conn.execute(
                """
                INSERT INTO pinterest_credentials
                    (account_id, pinterest_user_id, access_token_ciphertext, status)
                VALUES (%s, %s, %s, 'connected'), (%s, %s, %s, 'connected'),
                       (%s, %s, %s, 'connected')
                """,
                (account_a, "test-user-a", b"test-ciphertext-a",
                 account_b, "test-user-b", b"test-ciphertext-b",
                 account_c, "test-user-c", b"test-ciphertext-c"),
            )
            conn.execute(
                "INSERT INTO model2_account_profiles (account_id) VALUES (%s), (%s)",
                (account_a, account_b),
            )
            conn.execute(
                "INSERT INTO model2_niches (slug, display_name) VALUES (%s, %s), (%s, %s)",
                (niche_a, "Test Niche A", niche_b, "Test Niche B"),
            )
            ids = conn.execute(
                "SELECT id, slug FROM model2_niches WHERE slug IN (%s, %s)",
                (niche_a, niche_b),
            ).fetchall()
            niche_ids = {row["slug"]: row["id"] for row in ids}
            conn.execute(
                """
                INSERT INTO model2_account_niches (account_id, niche_id, is_primary)
                VALUES (%s, %s, TRUE), (%s, %s, TRUE)
                """,
                (account_a, niche_ids[niche_a], account_b, niche_ids[niche_b]),
            )
        yield {
            "account_a": account_a,
            "account_b": account_b,
            "account_c": account_c,
            "niche_a": niche_ids[niche_a],
            "niche_b": niche_ids[niche_b],
            "suffix": suffix,
        }
    finally:
        with database.connection() as conn:
            # Audit is append-only in application transactions. TRUNCATE is used
            # only against this dedicated disposable CI database during teardown.
            conn.execute("TRUNCATE TABLE affiliate_job_reconciliation_audit")
            # TEST_DATABASE_URL must point to a dedicated disposable database.
            # TRUNCATE bypasses immutable-row triggers only for test teardown.
            conn.execute(
                "TRUNCATE TABLE model2_learning_snapshot_sources, model2_publication_niche_attributions"
            )
            conn.execute(
                "DELETE FROM pin_analytics_snapshots WHERE pinterest_pin_id LIKE %s",
                (f"model2-test-pin-{suffix}%",),
            )
            conn.execute(
                "DELETE FROM pin_publications WHERE "
                "(account_id IN (%s, %s, %s) AND board_id LIKE %s) "
                "OR (account_id IN (%s, %s, %s) AND product_id IN "
                "(SELECT id FROM products WHERE product_name LIKE %s))",
                (account_a, account_b, account_c, f"test-board-{suffix}%",
                 account_a, account_b, account_c, "Reconciliation fixture %"),
            )
            conn.execute(
                "DELETE FROM content_versions WHERE product_id IN "
                "(SELECT id FROM products WHERE product_name LIKE %s OR product_name LIKE %s)",
                (f"Model2 test product {suffix}%", "Reconciliation fixture %"),
            )
            conn.execute(
                "DELETE FROM products WHERE product_name LIKE %s OR product_name LIKE %s",
                (f"Model2 test product {suffix}%", "Reconciliation fixture %"),
            )
            conn.execute(
                "DELETE FROM model2_learning_snapshots WHERE account_id IN (%s, %s)",
                (account_a, account_b),
            )
            conn.execute(
                "DELETE FROM affiliate_publishing_schedules WHERE account_id IN (%s, %s, %s)",
                (account_a, account_b, account_c),
            )
            conn.execute(
                "DELETE FROM model2_account_niches WHERE account_id IN (%s, %s, %s)",
                (account_a, account_b, account_c),
            )
            conn.execute(
                "DELETE FROM model2_account_profiles WHERE account_id IN (%s, %s, %s)",
                (account_a, account_b, account_c),
            )
            conn.execute(
                "DELETE FROM pinterest_credentials WHERE account_id IN (%s, %s, %s)",
                (account_a, account_b, account_c),
            )
            conn.execute(
                "DELETE FROM model2_niches WHERE slug LIKE %s",
                (f"%-{suffix}",),
            )
        database.close_pool()


def test_model2_registry_enforces_account_niche_membership(model2_db):
    with database.connection() as conn:
        conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count)
            VALUES (%s, %s, DATE '2026-01-01', DATE '2026-01-30',
                    '{"impression": 12}'::jsonb, 0, 0)
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        )

        with conn.transaction():
            with pytest.raises(ForeignKeyViolation):
                with conn.transaction():
                    conn.execute(
                        """
                        INSERT INTO model2_learning_snapshots
                            (account_id, niche_id, period_start, period_end, metrics,
                             sample_size, source_snapshot_count)
                        VALUES (%s, %s, DATE '2026-01-01', DATE '2026-01-30',
                                '{}'::jsonb, 0, 0)
                        """,
                        (model2_db["account_a"], model2_db["niche_b"]),
                    )

        # An account may be assigned multiple niches; only the primary niche
        # is unique. Once assigned, a snapshot for that account/niche is valid.
        conn.execute(
            """
            INSERT INTO model2_account_niches (account_id, niche_id, is_primary)
            VALUES (%s, %s, FALSE)
            """,
            (model2_db["account_a"], model2_db["niche_b"]),
        )
        conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count)
            VALUES (%s, %s, DATE '2026-01-01', DATE '2026-01-30',
                    '{}'::jsonb, 0, 0)
            """,
            (model2_db["account_a"], model2_db["niche_b"]),
        )


def test_model2_registry_enforces_one_active_primary_niche(model2_db):
    suffix = model2_db["account_a"].rsplit("-", 1)[-1]
    slug = f"second-primary-{suffix}"
    with database.connection() as conn:
        conn.execute(
            "INSERT INTO model2_niches (slug, display_name) VALUES (%s, %s)",
            (slug, "Second Primary Test"),
        )
        second_id = conn.execute(
            "SELECT id FROM model2_niches WHERE slug = %s", (slug,)
        ).fetchone()["id"]
        with conn.transaction():
            with pytest.raises(UniqueViolation):
                with conn.transaction():
                    conn.execute(
                        """
                        INSERT INTO model2_account_niches (account_id, niche_id, is_primary)
                        VALUES (%s, %s, TRUE)
                        """,
                        (model2_db["account_a"], second_id),
                    )
        conn.execute("DELETE FROM model2_niches WHERE id = %s", (second_id,))


def test_model2_registry_keeps_accounts_and_niches_independent(model2_db):
    with database.connection() as conn:
        rows = conn.execute(
            """
            SELECT account_id, niche_id
            FROM model2_account_niches
            WHERE account_id IN (%s, %s)
            ORDER BY account_id
            """,
            (model2_db["account_a"], model2_db["account_b"]),
        ).fetchall()
    assert rows == [
        {"account_id": model2_db["account_a"], "niche_id": model2_db["niche_a"]},
        {"account_id": model2_db["account_b"], "niche_id": model2_db["niche_b"]},
    ]



def _create_test_publication(conn, account_id: str, suffix: str) -> tuple[int, str]:
    product_id = conn.execute(
        """
        INSERT INTO products (product_name, product_details, image_url, affiliate_url)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (f"Model2 test product {suffix}", "Disposable test fixture",
         "https://example.invalid/test.png", "https://example.invalid/affiliate"),
    ).fetchone()["id"]
    content_version_id = conn.execute(
        """
        INSERT INTO content_versions
            (product_id, version_number, provider, model_id, prompt_version,
             pin_idea, title, description, alt_text)
        VALUES (%s, 1, 'test', 'test', 'test', 'test idea', 'test title',
                'test description', 'test alt')
        RETURNING id
        """,
        (product_id,),
    ).fetchone()["id"]
    pin_id = f"model2-test-pin-{suffix}"
    publication_id = conn.execute(
        """
        INSERT INTO pin_publications
            (product_id, content_version_id, board_id, account_id, status, pinterest_pin_id)
        VALUES (%s, %s, %s, %s, 'succeeded', %s)
        RETURNING id
        """,
        (product_id, content_version_id, f"test-board-{suffix}", account_id, pin_id),
    ).fetchone()["id"]
    return publication_id, pin_id


def test_model2_learning_sources_link_exact_raw_rows_and_are_immutable(model2_db):
    with database.connection() as conn:
        publication_id, pin_id = _create_test_publication(
            conn, model2_db["account_a"], model2_db["suffix"]
        )
        conn.execute(
            """
            INSERT INTO model2_publication_niche_attributions
                (publication_id, account_id, niche_id, attribution_source)
            VALUES (%s, %s, %s, 'workflow')
            """,
            (publication_id, model2_db["account_a"], model2_db["niche_a"]),
        )
        analytics_ids = []
        for start_day, end_day in (("2026-01-01", "2026-01-07"),
                                   ("2026-01-08", "2026-01-14")):
            analytics_ids.append(conn.execute(
                """
                INSERT INTO pin_analytics_snapshots
                    (publication_id, pinterest_pin_id, period_start, period_end, metrics)
                VALUES (%s, %s, %s::date, %s::date, '{"impression": 10}'::jsonb)
                RETURNING id
                """,
                (publication_id, pin_id, start_day, end_day),
            ).fetchone()["id"])

        learning_id = conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count)
            VALUES (%s, %s, DATE '2026-01-01', DATE '2026-01-14',
                    '{"impression": 20, "save": null}'::jsonb, 1, 2)
            RETURNING id
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO model2_learning_snapshot_sources
                (learning_snapshot_id, analytics_snapshot_id, publication_id, account_id, niche_id)
            VALUES (%s, %s, %s, %s, %s), (%s, %s, %s, %s, %s)
            """,
            (learning_id, analytics_ids[0], publication_id, model2_db["account_a"], model2_db["niche_a"],
             learning_id, analytics_ids[1], publication_id, model2_db["account_a"], model2_db["niche_a"]),
        )

        # Simulate Model 1 refreshing the same raw analytics row in place.
        conn.execute(
            "UPDATE pin_analytics_snapshots SET metrics = '{\"impression\": 999}'::jsonb WHERE id = %s",
            (analytics_ids[0],),
        )
        captured = conn.execute(
            """
            SELECT COUNT(*) AS source_count,
                   bool_and(source_metrics = '{"impression": 10}'::jsonb) AS source_metrics_captured
            FROM model2_learning_snapshot_sources
            WHERE learning_snapshot_id = %s
            """,
            (learning_id,),
        ).fetchone()
        assert captured["source_count"] == 2
        assert captured["source_metrics_captured"] is True

        with conn.transaction():
            with pytest.raises(RaiseException):
                with conn.transaction():
                    conn.execute(
                        """
                        UPDATE model2_learning_snapshot_sources
                        SET niche_id = %s
                        WHERE learning_snapshot_id = %s
                        """,
                        (model2_db["niche_b"], learning_id),
                    )

        with conn.transaction():
            with pytest.raises(RaiseException):
                with conn.transaction():
                    conn.execute(
                        """
                        UPDATE model2_publication_niche_attributions
                        SET attribution_source = 'operator_verified'
                        WHERE publication_id = %s
                        """,
                        (publication_id,),
                    )


def test_model2_learning_source_counts_are_checked_at_commit(model2_db):
    with pytest.raises(RaiseException):
        with database.connection() as conn:
            publication_id, pin_id = _create_test_publication(
                conn, model2_db["account_a"], model2_db["suffix"]
            )
            conn.execute(
                """
                INSERT INTO model2_publication_niche_attributions
                    (publication_id, account_id, niche_id, attribution_source)
                VALUES (%s, %s, %s, 'workflow')
                """,
                (publication_id, model2_db["account_a"], model2_db["niche_a"]),
            )
            analytics_id = conn.execute(
                """
                INSERT INTO pin_analytics_snapshots
                    (publication_id, pinterest_pin_id, period_start, period_end, metrics)
                VALUES (%s, %s, DATE '2026-02-01', DATE '2026-02-07',
                        '{"impression": 5}'::jsonb)
                RETURNING id
                """,
                (publication_id, pin_id),
            ).fetchone()["id"]
            learning_id = conn.execute(
                """
                INSERT INTO model2_learning_snapshots
                    (account_id, niche_id, period_start, period_end, metrics,
                     sample_size, source_snapshot_count)
                VALUES (%s, %s, DATE '2026-02-01', DATE '2026-02-07',
                        '{"impression": 5}'::jsonb, 1, 2)
                RETURNING id
                """,
                (model2_db["account_a"], model2_db["niche_a"]),
            ).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO model2_learning_snapshot_sources
                    (learning_snapshot_id, analytics_snapshot_id, publication_id, account_id, niche_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (learning_id, analytics_id, publication_id,
                 model2_db["account_a"], model2_db["niche_a"]),
            )


def test_model2_learning_source_rejects_cross_account_lineage(model2_db):
    with database.connection() as conn:
        publication_id, pin_id = _create_test_publication(
            conn, model2_db["account_a"], model2_db["suffix"]
        )
        conn.execute(
            """
            INSERT INTO model2_publication_niche_attributions
                (publication_id, account_id, niche_id, attribution_source)
            VALUES (%s, %s, %s, 'workflow')
            """,
            (publication_id, model2_db["account_a"], model2_db["niche_a"]),
        )
        analytics_id = conn.execute(
            """
            INSERT INTO pin_analytics_snapshots
                (publication_id, pinterest_pin_id, period_start, period_end, metrics)
            VALUES (%s, %s, DATE '2026-03-01', DATE '2026-03-07',
                    '{"impression": 5}'::jsonb)
            RETURNING id
            """,
            (publication_id, pin_id),
        ).fetchone()["id"]
        learning_id = conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count)
            VALUES (%s, %s, DATE '2026-03-01', DATE '2026-03-07',
                    '{"impression": 5}'::jsonb, 0, 0)
            RETURNING id
            """,
            (model2_db["account_b"], model2_db["niche_b"]),
        ).fetchone()["id"]
        with conn.transaction():
            with pytest.raises(ForeignKeyViolation):
                with conn.transaction():
                    conn.execute(
                        """
                        INSERT INTO model2_learning_snapshot_sources
                            (learning_snapshot_id, analytics_snapshot_id, publication_id, account_id, niche_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (learning_id, analytics_id, publication_id,
                         model2_db["account_b"], model2_db["niche_b"]),
                    )



def test_model2_account_profile_requires_canonical_existing_credential(model2_db):
    with database.connection() as conn:
        with conn.transaction():
            with pytest.raises(ForeignKeyViolation):
                with conn.transaction():
                    conn.execute(
                        "INSERT INTO model2_account_profiles (account_id) VALUES (%s)",
                        (f"pinterest:missing-{model2_db['suffix']}",),
                    )

        with conn.transaction():
            with pytest.raises(CheckViolation):
                with conn.transaction():
                    conn.execute(
                        "INSERT INTO model2_account_profiles (account_id) VALUES (%s)",
                        (f"not-pinterest-{model2_db['suffix']}",),
                    )




@pytest.mark.parametrize(
    ("isolation_level", "expected_exception"),
    [
        ("READ COMMITTED", RaiseException),
        ("REPEATABLE READ", SerializationFailure),
    ],
)
def test_model2_learning_source_concurrent_inserts_are_serialized(
    model2_db, isolation_level, expected_exception
):
    """Concurrent writers cannot exceed a snapshot's declared source count."""
    import threading
    import time

    import psycopg

    with database.connection() as conn:
        publications = []
        analytics_ids = []
        for index in (1, 2):
            publication_id, pin_id = _create_test_publication(
                conn, model2_db["account_a"], f"{model2_db['suffix']}-race-{index}"
            )
            conn.execute(
                """
                INSERT INTO model2_publication_niche_attributions
                    (publication_id, account_id, niche_id, attribution_source)
                VALUES (%s, %s, %s, 'workflow')
                """,
                (publication_id, model2_db["account_a"], model2_db["niche_a"]),
            )
            analytics_id = conn.execute(
                """
                INSERT INTO pin_analytics_snapshots
                    (publication_id, pinterest_pin_id, period_start, period_end, metrics)
                VALUES (%s, %s, DATE '2026-04-01', DATE '2026-04-07',
                        '{"impression": 1}'::jsonb)
                RETURNING id
                """,
                (publication_id, pin_id),
            ).fetchone()["id"]
            publications.append(publication_id)
            analytics_ids.append(analytics_id)

        learning_id = conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count)
            VALUES (%s, %s, DATE '2026-04-01', DATE '2026-04-07',
                    '{"impression": 1}'::jsonb, 0, 0)
            RETURNING id
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        ).fetchone()["id"]

    first_inserted = threading.Event()
    release_first = threading.Event()
    second_pid_ready = threading.Event()
    second_finished = threading.Event()
    outcomes = {}

    def insert_source(name, analytics_id, publication_id):
        try:
            with psycopg.connect(TEST_DATABASE_URL) as conn:
                conn.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")
                if name == "first":
                    conn.execute(
                        """
                        INSERT INTO model2_learning_snapshot_sources
                            (learning_snapshot_id, analytics_snapshot_id, publication_id, account_id, niche_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (learning_id, analytics_id, publication_id,
                         model2_db["account_a"], model2_db["niche_a"]),
                    )
                    conn.execute(
                        """
                        UPDATE model2_learning_snapshots
                        SET sample_size = 1, source_snapshot_count = 1
                        WHERE id = %s
                        """,
                        (learning_id,),
                    )
                    first_inserted.set()
                    if not release_first.wait(timeout=10):
                        raise TimeoutError("test did not release first source transaction")
                else:
                    # Establish a repeatable snapshot before the first writer commits.
                    conn.execute(
                        "SELECT id FROM model2_learning_snapshots WHERE id = %s",
                        (learning_id,),
                    )
                    outcomes["second_pid"] = conn.execute(
                        "SELECT pg_backend_pid()"
                    ).fetchone()[0]
                    second_pid_ready.set()
                    conn.execute(
                        """
                        INSERT INTO model2_learning_snapshot_sources
                            (learning_snapshot_id, analytics_snapshot_id, publication_id, account_id, niche_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (learning_id, analytics_id, publication_id,
                         model2_db["account_a"], model2_db["niche_a"]),
                    )
            outcomes[name] = "committed"
        except Exception as exc:
            outcomes[name] = exc
        finally:
            if name == "second":
                second_finished.set()

    first = threading.Thread(
        target=insert_source,
        args=("first", analytics_ids[0], publications[0]),
        daemon=True,
    )
    second = threading.Thread(
        target=insert_source,
        args=("second", analytics_ids[1], publications[1]),
        daemon=True,
    )
    first.start()
    assert first_inserted.wait(timeout=10), "first writer did not insert its source row"
    second.start()
    assert second_pid_ready.wait(timeout=10), "second writer did not establish its snapshot"

    # Observe a real database lock wait, rather than relying on thread timing.
    deadline = time.monotonic() + 10
    blocked = False
    while time.monotonic() < deadline:
        with psycopg.connect(TEST_DATABASE_URL) as monitor:
            wait_state = monitor.execute(
                """
                SELECT cardinality(pg_blocking_pids(pid))
                FROM pg_stat_activity
                WHERE pid = %s
                """,
                (outcomes["second_pid"],),
            ).fetchone()
        if wait_state and wait_state[0] > 0:
            blocked = True
            break
        if second_finished.is_set():
            break
        time.sleep(0.02)

    try:
        assert blocked, "second writer never waited on the parent snapshot lock"
    finally:
        release_first.set()

    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive(), "concurrent writers did not finish"
    assert outcomes.get("first") == "committed", f"first writer failed: {outcomes.get('first')!r}"
    assert isinstance(outcomes.get("second"), expected_exception), (
        f"expected {expected_exception.__name__}, got {outcomes.get('second')!r}"
    )

    with database.connection() as conn:
        counts = conn.execute(
            """
            SELECT COUNT(*) AS source_count,
                   COUNT(DISTINCT publication_id) AS publication_count
            FROM model2_learning_snapshot_sources
            WHERE learning_snapshot_id = %s
            """,
            (learning_id,),
        ).fetchone()
    assert counts["source_count"] == 1
    assert counts["publication_count"] == 1


def test_model2_repository_onboards_profile_using_metadata_only_credential_check(model2_db):
    from app.model2_repository import get_account_profile

    created = save_account_profile(
        AccountProfileInput(
            account_id=model2_db["account_c"],
            display_name="Repository Test Account",
            timezone="Asia/Karachi",
        )
    )
    assert created["account_id"] == model2_db["account_c"]
    assert created["display_name"] == "Repository Test Account"
    assert created["timezone"] == "Asia/Karachi"
    assert get_account_profile(model2_db["account_c"])["status"] == "active"


def test_model2_repository_rejects_reactivation_after_credential_revocation(model2_db):
    with database.connection() as conn:
        conn.execute(
            "UPDATE pinterest_credentials SET status = 'revoked' WHERE account_id = %s",
            (model2_db["account_a"],),
        )

    with pytest.raises(Model2AccountNotConnectedError):
        save_account_profile(
            AccountProfileInput(
                account_id=model2_db["account_a"],
                status="active",
            )
        )

    paused = save_account_profile(
        AccountProfileInput(
            account_id=model2_db["account_a"],
            status="paused",
        )
    )
    assert paused["status"] == "paused"

    with database.connection() as conn:
        states = conn.execute(
            """
            SELECT status
            FROM model2_account_niches
            WHERE account_id = %s
            """,
            (model2_db["account_a"],),
        ).fetchall()
    assert states and all(row["status"] == "paused" for row in states)


def test_model2_repository_primary_swap_and_account_scoped_listing(model2_db):
    slug = f"repository-primary-{model2_db['suffix']}"
    niche = create_niche(NicheInput(slug=slug, display_name="Repository Primary"))
    save_account_niche_assignment(
        AccountNicheAssignmentInput(
            account_id=model2_db["account_a"],
            niche_id=niche["id"],
            is_primary=True,
        )
    )

    account_a_rows = list_account_niche_assignments(model2_db["account_a"])
    account_b_rows = list_account_niche_assignments(model2_db["account_b"])
    assert {row["account_id"] for row in account_a_rows} == {model2_db["account_a"]}
    assert {row["account_id"] for row in account_b_rows} == {model2_db["account_b"]}

    active_primaries = [
        row for row in account_a_rows
        if row["is_primary"] and row["status"] == "active"
    ]
    assert len(active_primaries) == 1
    assert active_primaries[0]["niche_id"] == niche["id"]
    assert any(
        row["niche_id"] == model2_db["niche_a"] and not row["is_primary"]
        for row in account_a_rows
    )
    assert any(
        row["niche_id"] == model2_db["niche_b"]
        and row["is_primary"]
        and row["status"] == "active"
        for row in account_b_rows
    )


def test_model2_repository_archiving_niche_pauses_assignments_without_deleting_history(model2_db):
    with database.connection() as conn:
        slug = conn.execute(
            "SELECT slug FROM model2_niches WHERE id = %s",
            (model2_db["niche_a"],),
        ).fetchone()["slug"]

    update_niche(
        model2_db["niche_a"],
        NicheInput(
            slug=slug,
            display_name="Test Niche A",
            status="archived",
        ),
    )

    with database.connection() as conn:
        row = conn.execute(
            """
            SELECT is_primary, status
            FROM model2_account_niches
            WHERE account_id = %s AND niche_id = %s
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        ).fetchone()
    assert row == {"is_primary": True, "status": "paused"}


def test_model2_repository_rejects_active_assignment_to_archived_niche(model2_db):
    with database.connection() as conn:
        slug = conn.execute(
            "SELECT slug FROM model2_niches WHERE id = %s",
            (model2_db["niche_a"],),
        ).fetchone()["slug"]

    update_niche(
        model2_db["niche_a"],
        NicheInput(slug=slug, display_name="Test Niche A", status="archived"),
    )

    with pytest.raises(Model2ConflictError, match="archived niche"):
        save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id=model2_db["account_a"],
                niche_id=model2_db["niche_a"],
                status="active",
            )
        )


def test_model2_repository_serializes_concurrent_primary_selection(model2_db):
    from concurrent.futures import ThreadPoolExecutor

    first = create_niche(
        NicheInput(
            slug=f"concurrent-primary-a-{model2_db['suffix']}",
            display_name="Concurrent Primary A",
        )
    )
    second = create_niche(
        NicheInput(
            slug=f"concurrent-primary-b-{model2_db['suffix']}",
            display_name="Concurrent Primary B",
        )
    )

    def assign(niche_id):
        return save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id=model2_db["account_a"],
                niche_id=niche_id,
                is_primary=True,
            )
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(assign, [first["id"], second["id"]]))

    assert len(results) == 2
    rows = list_account_niche_assignments(model2_db["account_a"])
    active_primaries = [
        row for row in rows
        if row["is_primary"] and row["status"] == "active"
    ]
    assert len(active_primaries) == 1
    assert active_primaries[0]["niche_id"] in {first["id"], second["id"]}


def test_model2_repository_rejects_active_assignment_when_credential_is_revoked(model2_db):
    with database.connection() as conn:
        conn.execute(
            "UPDATE pinterest_credentials SET status = 'revoked' WHERE account_id = %s",
            (model2_db["account_a"],),
        )

    with pytest.raises(Model2AccountNotConnectedError):
        save_account_niche_assignment(
            AccountNicheAssignmentInput(
                account_id=model2_db["account_a"],
                niche_id=model2_db["niche_b"],
                status="active",
            )
        )


def _model2_publication_fixture(model2_db, label):
    suffix = model2_db["suffix"]
    product = database.create_product(
        product_name=f"Model2 test product {suffix} {label}",
        product_details="Disposable PostgreSQL test fixture; no real product.",
        image_url=None,
        affiliate_url="https://example.invalid/model2-test",
        idempotency_key=f"model2-publish-{suffix}-{label}",
    )
    content = database.create_content_version(
        product_id=product["id"],
        provider="test-stub",
        model_id="model2-test",
        prompt_version="model2-test",
        pin_idea="fixture only",
        title="fixture only",
        description="fixture only",
        alt_text="fixture only",
    )
    return product, content


def test_model2_active_niche_context_is_exactly_account_scoped(model2_db):
    context = get_active_account_niche_context(
        model2_db["account_a"], model2_db["niche_a"]
    )
    assert context["niche_id"] == model2_db["niche_a"]
    assert context["slug"] == f"test-niche-a-{model2_db['suffix']}"
    assert context["default_region"] == "US"

    with pytest.raises(Model2NotFoundError):
        get_active_account_niche_context(
            model2_db["account_a"], model2_db["niche_b"]
        )


def test_model2_active_niche_context_rejects_paused_assignment(model2_db):
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE model2_account_niches SET status = 'paused'
            WHERE account_id = %s AND niche_id = %s
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        )

    with pytest.raises(Model2ConflictError, match="must all be active"):
        get_active_account_niche_context(
            model2_db["account_a"], model2_db["niche_a"]
        )


def test_model2_publication_reservation_inserts_attribution_atomically(model2_db):
    product, content = _model2_publication_fixture(model2_db, "new-attribution")
    board_id = f"test-board-{model2_db['suffix']}-new-attribution"

    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    assert reserved["blocked"] is False

    with database.connection() as conn:
        attribution = conn.execute(
            """
            SELECT publication_id, account_id, niche_id, attribution_source
            FROM model2_publication_niche_attributions
            WHERE publication_id = %s
            """,
            (reserved["id"],),
        ).fetchone()
    assert attribution == {
        "publication_id": reserved["id"],
        "account_id": model2_db["account_a"],
        "niche_id": model2_db["niche_a"],
        "attribution_source": "workflow",
    }


def test_model2_publication_reservation_rejects_inactive_assignment_before_ledger_insert(model2_db):
    product, content = _model2_publication_fixture(model2_db, "inactive-assignment")
    board_id = f"test-board-{model2_db['suffix']}-inactive-assignment"
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE model2_account_niches SET status = 'paused'
            WHERE account_id = %s AND niche_id = %s
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        )

    result = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    assert result == {"blocked": True, "niche_assignment_inactive": True}
    with database.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM pin_publications WHERE content_version_id = %s",
            (content["id"],),
        ).fetchone()["n"]
    assert count == 0


def test_model2_legacy_succeeded_publication_is_never_retroactively_attributed(model2_db):
    product, content = _model2_publication_fixture(model2_db, "legacy-success")
    board_id = f"test-board-{model2_db['suffix']}-legacy-success"
    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
    )
    database.finish_publish_attempt(
        reserved["id"],
        status="succeeded",
        pinterest_pin_id=f"model2-test-pin-{model2_db['suffix']}-legacy",
        http_status=201,
    )

    blocked = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    assert blocked["blocked"] is True
    assert blocked["niche_attribution_missing"] is True
    with database.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM model2_publication_niche_attributions WHERE publication_id = %s",
            (reserved["id"],),
        ).fetchone()["n"]
    assert count == 0


def test_model2_failed_legacy_publication_can_gain_explicit_attribution_on_retry(model2_db):
    product, content = _model2_publication_fixture(model2_db, "failed-retry")
    board_id = f"test-board-{model2_db['suffix']}-failed-retry"
    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
    )
    database.finish_publish_attempt(
        reserved["id"],
        status="failed",
        http_status=400,
        error_code="test_rejected",
    )

    retried = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    assert retried["blocked"] is False
    assert retried["attempt_count"] == 2
    with database.connection() as conn:
        attribution = conn.execute(
            """
            SELECT account_id, niche_id, attribution_source
            FROM model2_publication_niche_attributions
            WHERE publication_id = %s
            """,
            (reserved["id"],),
        ).fetchone()
    assert attribution == {
        "account_id": model2_db["account_a"],
        "niche_id": model2_db["niche_a"],
        "attribution_source": "workflow",
    }


def test_model2_failed_publication_cannot_change_immutable_niche_attribution(model2_db):
    product, content = _model2_publication_fixture(model2_db, "attribution-mismatch")
    board_id = f"test-board-{model2_db['suffix']}-attribution-mismatch"
    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    database.finish_publish_attempt(
        reserved["id"],
        status="failed",
        http_status=400,
        error_code="test_rejected",
    )

    blocked = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_b"],
    )
    assert blocked["blocked"] is True
    assert blocked["niche_attribution_mismatch"] is True


def test_model2_attributed_failed_publication_cannot_retry_after_assignment_pause(model2_db):
    product, content = _model2_publication_fixture(model2_db, "paused-retry")
    board_id = f"test-board-{model2_db['suffix']}-paused-retry"
    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    database.finish_publish_attempt(
        reserved["id"],
        status="failed",
        http_status=400,
        error_code="test_rejected",
    )
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE model2_account_niches SET status = 'paused'
            WHERE account_id = %s AND niche_id = %s
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        )

    blocked = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
    )
    assert blocked["blocked"] is True
    assert blocked["niche_assignment_inactive"] is True


def test_model2_publication_reservation_requires_connected_credential(model2_db):
    product, content = _model2_publication_fixture(model2_db, "revoked-account")
    board_id = f"test-board-{model2_db['suffix']}-revoked-account"
    with database.connection() as conn:
        conn.execute(
            "UPDATE pinterest_credentials SET status = 'revoked' WHERE account_id = %s",
            (model2_db["account_a"],),
        )

    result = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    assert result == {"blocked": True, "niche_account_not_connected": True}


def _model2_pin_with_raw_analytics(
    model2_db,
    *,
    label,
    account_id,
    niche_id,
    period_start,
    period_end,
    metrics,
):
    suffix = model2_db["suffix"]
    product = database.create_product(
        product_name=f"Model2 test product {suffix} {label}",
        product_details="Disposable analytics projection fixture.",
        image_url="https://example.invalid/model2-learning-fixture.png",
        affiliate_url="https://example.invalid/model2-learning",
        idempotency_key=f"model2-learning-{suffix}-{label}",
    )
    content = database.create_content_version(
        product_id=product["id"],
        provider="test-stub",
        model_id="model2-learning-test",
        prompt_version="model2-learning-test",
        pin_idea="fixture only",
        title="fixture only",
        description="fixture only",
        alt_text="fixture only",
    )
    board_id = f"test-board-{suffix}-{label}"
    reservation_kwargs = {
        "product_id": product["id"],
        "content_version_id": content["id"],
        "board_id": board_id,
        "account_id": account_id,
    }
    if niche_id is not None:
        reservation_kwargs["niche_id"] = niche_id
    reserved = database.begin_publish_attempt(**reservation_kwargs)
    assert reserved["blocked"] is False

    pin_id = f"model2-test-pin-{suffix}-{label}"
    database.finish_publish_attempt(
        reserved["id"],
        status="succeeded",
        pinterest_pin_id=pin_id,
        http_status=201,
    )
    with database.connection() as conn:
        raw = conn.execute(
            """
            INSERT INTO pin_analytics_snapshots
                (publication_id, pinterest_pin_id, period_start, period_end, metrics)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                reserved["id"], pin_id, period_start, period_end,
                __import__("json").dumps(metrics),
            ),
        ).fetchone()
    return {
        "publication_id": reserved["id"],
        "analytics_snapshot_id": raw["id"],
        "pin_id": pin_id,
        "product_id": product["id"],
        "content_version_id": content["id"],
    }


def test_model2_learning_projection_is_account_niche_period_scoped_and_immutable(model2_db):
    period_start = date(2026, 10, 1)
    period_end = date(2026, 10, 30)
    first_metrics = {
        "impression": 100,
        "save": 10,
        "pin_click": None,
        "outbound_click": 4,
    }
    second_metrics = {
        "impression": 50,
        "save": 5,
        "pin_click": 2,
        "outbound_click": 1,
    }
    first = _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-a1",
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
        metrics=first_metrics,
    )
    second = _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-a2",
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
        metrics=second_metrics,
    )
    # Same account, different niche must not leak into this projection.
    _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-b",
        account_id=model2_db["account_b"],
        niche_id=model2_db["niche_b"],
        period_start=period_start,
        period_end=period_end,
        metrics={"impression": 1000, "save": 100, "pin_click": 50, "outbound_click": 25},
    )
    # Same account+niche but a different raw observation period is excluded.
    _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-other-period",
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=date(2026, 10, 2),
        period_end=period_end,
        metrics={"impression": 900, "save": 90, "pin_click": 40, "outbound_click": 20},
    )
    # Real raw analytics without explicit niche attribution are excluded.
    _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-unattributed",
        account_id=model2_db["account_a"],
        niche_id=None,
        period_start=period_start,
        period_end=period_end,
        metrics={"impression": 800, "save": 80, "pin_click": 30, "outbound_click": 15},
    )

    snapshot = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
    )

    assert snapshot["created"] is True
    assert snapshot["sample_size"] == 2
    assert snapshot["source_snapshot_count"] == 2
    assert snapshot["learning_status"] == "descriptive_only"
    assert snapshot["metrics"] == {
        "impression": 150,
        "save": 15,
        "pin_click": None,
        "outbound_click": 5,
    }

    with database.connection() as conn:
        sources = conn.execute(
            """
            SELECT analytics_snapshot_id, publication_id, source_metrics
            FROM model2_learning_snapshot_sources
            WHERE learning_snapshot_id = %s
            ORDER BY analytics_snapshot_id
            """,
            (snapshot["snapshot_id"],),
        ).fetchall()
    assert {row["analytics_snapshot_id"] for row in sources} == {
        first["analytics_snapshot_id"],
        second["analytics_snapshot_id"],
    }
    captured = {row["publication_id"]: row["source_metrics"] for row in sources}
    assert captured[first["publication_id"]] == first_metrics
    assert captured[second["publication_id"]] == second_metrics

    # Model 1 refreshes raw analytics in place; Model 2 source lineage stays immutable.
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE pin_analytics_snapshots
            SET metrics = '{"impression":999,"save":999,"pin_click":999,"outbound_click":999}'::jsonb
            WHERE id = %s
            """,
            (first["analytics_snapshot_id"],),
        )
        raw_after_refresh = conn.execute(
            "SELECT metrics FROM pin_analytics_snapshots WHERE id = %s",
            (first["analytics_snapshot_id"],),
        ).fetchone()["metrics"]
        source_after_refresh = conn.execute(
            """
            SELECT source_metrics FROM model2_learning_snapshot_sources
            WHERE learning_snapshot_id = %s AND analytics_snapshot_id = %s
            """,
            (snapshot["snapshot_id"], first["analytics_snapshot_id"]),
        ).fetchone()["source_metrics"]
    assert raw_after_refresh["impression"] == 999
    assert source_after_refresh == first_metrics

    # Same exact period is idempotent and returns the first immutable evidence.
    repeated = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
    )
    assert repeated["created"] is False
    assert repeated["snapshot_id"] == snapshot["snapshot_id"]
    assert repeated["metrics"] == snapshot["metrics"]
    assert repeated["source_snapshot_count"] == 2

    listed_a = list_learning_snapshots(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    listed_b = list_learning_snapshots(
        account_id=model2_db["account_b"],
        niche_id=model2_db["niche_b"],
    )
    assert [row["snapshot_id"] for row in listed_a] == [snapshot["snapshot_id"]]
    assert listed_b == []


def test_model2_learning_projection_without_attributed_raw_rows_is_not_persisted(model2_db):
    result = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
    )

    assert result["snapshot_id"] is None
    assert result["learning_status"] == "insufficient_data"
    assert result["sample_size"] == 0
    assert result["source_snapshot_count"] == 0
    assert all(value is None for value in result["metrics"].values())

    with database.connection() as conn:
        count = conn.execute(
            """
            SELECT count(*) AS n FROM model2_learning_snapshots
            WHERE account_id = %s AND niche_id = %s
              AND period_start = DATE '2026-09-01'
              AND period_end = DATE '2026-09-30'
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        ).fetchone()["n"]
    assert count == 0


def test_model2_learning_projection_requires_exact_existing_assignment(model2_db):
    with pytest.raises(Model2NotFoundError):
        create_learning_snapshot(
            account_id=model2_db["account_a"],
            niche_id=model2_db["niche_b"],
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 30),
        )


def test_model2_learning_projection_preserves_historical_attribution_after_pause_and_archive(model2_db):
    period_start = date(2026, 10, 1)
    period_end = date(2026, 10, 30)
    _model2_pin_with_raw_analytics(
        model2_db,
        label="projection-historical-paused",
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
        metrics={"impression": 12, "save": 2, "pin_click": 1, "outbound_click": 1},
    )
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE model2_account_niches SET status = 'paused'
            WHERE account_id = %s AND niche_id = %s
            """,
            (model2_db["account_a"], model2_db["niche_a"]),
        )
        conn.execute(
            "UPDATE model2_niches SET status = 'archived' WHERE id = %s",
            (model2_db["niche_a"],),
        )

    snapshot = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
    )

    assert snapshot["created"] is True
    assert snapshot["sample_size"] == 1
    assert snapshot["metrics"]["impression"] == 12


def test_model2_learning_projection_excludes_pending_publication_even_if_raw_row_exists(model2_db):
    product, content = _model2_publication_fixture(model2_db, "projection-pending")
    board_id = f"test-board-{model2_db['suffix']}-projection-pending"
    reserved = database.begin_publish_attempt(
        product_id=product["id"],
        content_version_id=content["id"],
        board_id=board_id,
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
    )
    with database.connection() as conn:
        conn.execute(
            """
            INSERT INTO pin_analytics_snapshots
                (publication_id, pinterest_pin_id, period_start, period_end, metrics)
            VALUES (%s, %s, DATE '2026-10-01', DATE '2026-10-30',
                    '{"impression":50,"save":5,"pin_click":1,"outbound_click":2}'::jsonb)
            """,
            (reserved["id"], f"model2-test-pin-{model2_db['suffix']}-pending"),
        )

    result = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 30),
    )

    assert result["snapshot_id"] is None
    assert result["learning_status"] == "insufficient_data"


def test_model2_dashboard_lists_profiles_niches_and_evidence_without_secrets(model2_db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    period_start = date(2026, 10, 1)
    period_end = date(2026, 10, 30)
    first = _model2_pin_with_raw_analytics(
        model2_db,
        label="dashboard-attributed",
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
        metrics={"impression": 200, "save": None, "pin_click": 8, "outbound_click": 3},
    )
    projection = create_learning_snapshot(
        account_id=model2_db["account_a"],
        niche_id=model2_db["niche_a"],
        period_start=period_start,
        period_end=period_end,
    )
    assert projection["snapshot_id"] is not None

    extra_slug = f"test-niche-extra-{model2_db['suffix']}"
    with database.connection() as conn:
        conn.execute(
            "INSERT INTO model2_niches (slug, display_name, default_region) VALUES (%s, %s, 'GB+IE')",
            (extra_slug, "Extra Test Niche"),
        )
        extra_id = conn.execute(
            "SELECT id FROM model2_niches WHERE slug = %s",
            (extra_slug,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO model2_account_niches (account_id, niche_id) VALUES (%s, %s)",
            (model2_db["account_a"], extra_id),
        )
        conn.execute(
            "INSERT INTO model2_account_profiles (account_id, display_name, status) VALUES (%s, 'No niche profile', 'paused')",
            (model2_db["account_c"],),
        )
        conn.execute(
            "UPDATE model2_account_niches SET status = 'paused' WHERE account_id = %s AND niche_id = %s",
            (model2_db["account_a"], model2_db["niche_a"]),
        )
        conn.execute(
            "UPDATE model2_niches SET status = 'archived' WHERE id = %s",
            (model2_db["niche_a"],),
        )

    monkeypatch.setattr(settings, "app_api_key", "model2-dashboard-postgres-test-key")
    client = TestClient(app, base_url="https://testserver")
    login = client.post(
        "/dashboard/session",
        json={"api_key": "model2-dashboard-postgres-test-key"},
    )
    assert login.status_code == 200

    response = client.get("/dashboard/api/model2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_available"] is True
    rows_a = [row for row in payload["accounts"] if row["account_id"] == model2_db["account_a"]]
    rows_c = [row for row in payload["accounts"] if row["account_id"] == model2_db["account_c"]]
    assert len(rows_a) == 2
    assert len(rows_c) == 1
    assert rows_c[0]["niche_id"] is None
    archived = next(row for row in rows_a if row["niche_id"] == model2_db["niche_a"])
    assert archived["account_status"] == "active"
    assert archived["assignment_status"] == "paused"
    assert archived["niche_status"] == "archived"
    assert archived["is_primary"] is True
    assert archived["attributed_publication_count"] == 1
    assert archived["snapshot_count"] == 1
    assert archived["latest_period_end"] == period_end.isoformat()
    assert archived["latest_metrics"]["impression"] == 200
    assert archived["latest_metrics"]["save"] is None
    assert first["publication_id"] > 0
    assert "access_token" not in response.text
    assert "test-ciphertext-a" not in response.text
    assert "affiliate_url" not in response.text


# Phase 9: account-aware scheduler integration. Every workflow call below is
# mocked; these tests never contact Pinterest or create a Board/Pin.
def _model2_schedule_payload(account_id, niche_id, *, timezone_name="UTC", daily_limit=1):
    from app.affiliate_scheduler import CreateScheduleInput

    return CreateScheduleInput(
        account_id=account_id,
        niche_id=niche_id,
        timezone=timezone_name,
        starts_on=datetime.now(timezone.utc).date() + timedelta(days=1),
        days=1,
        daily_pin_limit=daily_limit,
        board_name="Existing Test Board",
        sources=[{
            "product_name": "Model2 scheduler test product",
            "product_details": "Disposable scheduler integration fixture",
            "affiliate_url": "https://example.invalid/model2-scheduler-test",
        }],
    )


def _create_and_activate_model2_schedule(account_id, niche_id, *, daily_limit=1):
    from app.affiliate_scheduler import create_draft_schedule, activate_schedule

    draft = create_draft_schedule(_model2_schedule_payload(account_id, niche_id, daily_limit=daily_limit))
    active = activate_schedule(draft["schedule_id"])
    return draft["schedule_id"], active


def test_model2_schedule_requires_exact_active_account_niche_and_profile_timezone(model2_db):
    from app.affiliate_scheduler import create_draft_schedule

    draft = create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_a"]))
    assert draft["niche_id"] == model2_db["niche_a"]
    assert draft["jobs_created"] == 0
    assert draft["publishing_started"] is False

    with pytest.raises(HTTPException) as mismatch:
        create_draft_schedule(_model2_schedule_payload(
            model2_db["account_a"], model2_db["niche_a"], timezone_name="America/Los_Angeles"
        ))
    assert mismatch.value.status_code == 409

    with pytest.raises(HTTPException) as cross_account:
        create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_b"]))
    assert cross_account.value.status_code == 409


def test_model2_schedule_activation_rechecks_paused_assignment_and_connected_metadata(model2_db):
    from app import database
    from app.affiliate_scheduler import create_draft_schedule, activate_schedule

    draft = create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_a"]))
    with database.connection() as conn:
        conn.execute(
            "UPDATE model2_account_niches SET status = 'paused' WHERE account_id = %s AND niche_id = %s",
            (model2_db["account_a"], model2_db["niche_a"]),
        )
    with pytest.raises(HTTPException) as paused:
        activate_schedule(draft["schedule_id"])
    assert paused.value.status_code == 409

    with database.connection() as conn:
        conn.execute(
            "UPDATE model2_account_niches SET status = 'active' WHERE account_id = %s AND niche_id = %s",
            (model2_db["account_a"], model2_db["niche_a"]),
        )
    credential_draft = create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_a"]))
    with database.connection() as conn:
        conn.execute(
            "UPDATE pinterest_credentials SET status = 'revoked' WHERE account_id = %s",
            (model2_db["account_a"],),
        )
    with pytest.raises(HTTPException) as revoked:
        activate_schedule(credential_draft["schedule_id"])
    assert revoked.value.status_code == 409


def test_model2_schedule_replacement_waits_for_old_processing_job(model2_db):
    from app import database
    from app.affiliate_scheduler import create_draft_schedule, activate_schedule, pause_schedule

    old_id, _ = _create_and_activate_model2_schedule(model2_db["account_a"], model2_db["niche_a"])
    pause_schedule(old_id)
    with database.connection() as conn:
        conn.execute(
            """
            WITH one_job AS (
                SELECT id FROM affiliate_pin_jobs
                WHERE schedule_id = %s ORDER BY id LIMIT 1
            )
            UPDATE affiliate_pin_jobs j SET status = 'processing', locked_at = now()
            FROM one_job WHERE j.id = one_job.id
            """,
            (old_id,),
        )
    new_draft = create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_a"]))
    with pytest.raises(HTTPException) as outstanding:
        activate_schedule(new_draft["schedule_id"])
    assert outstanding.value.status_code == 409

    with database.connection() as conn:
        conn.execute(
            "UPDATE affiliate_pin_jobs SET status = 'failed', finished_at = now() WHERE schedule_id = %s AND status = 'processing'",
            (old_id,),
        )
    assert activate_schedule(new_draft["schedule_id"])["status"] == "active"


def test_model2_account_daily_quota_counts_prior_schedule_completion_by_event_time(model2_db, monkeypatch):
    from app import database, workflow
    from app.affiliate_scheduler import pause_schedule, run_one_due_job

    old_id, _ = _create_and_activate_model2_schedule(model2_db["account_a"], model2_db["niche_a"])
    pause_schedule(old_id)
    with database.connection() as conn:
        conn.execute(
            """
            UPDATE affiliate_pin_jobs
            SET status = 'succeeded', finished_at = now(), local_run_date = CURRENT_DATE - 1
            WHERE schedule_id = %s AND status = 'cancelled'
            """,
            (old_id,),
        )
    new_id, _ = _create_and_activate_model2_schedule(model2_db["account_a"], model2_db["niche_a"])
    with database.connection() as conn:
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE schedule_id = %s",
            (new_id,),
        )

    calls = []
    monkeypatch.setattr(workflow, "publish_product_end_to_end", lambda *a, **k: calls.append((a, k)))
    result = run_one_due_job()
    assert result == {"claimed": False, "processed": False, "reason": "no_due_job"}
    assert calls == []


def test_model2_worker_passes_exact_niche_and_serializes_concurrent_account_quota(model2_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app import database, workflow
    from app.affiliate_scheduler import run_one_due_job

    schedule_id, _ = _create_and_activate_model2_schedule(
        model2_db["account_a"], model2_db["niche_a"], daily_limit=1
    )
    from psycopg.errors import CheckViolation
    with database.connection() as conn:
        with pytest.raises(CheckViolation):
            with conn.transaction():
                conn.execute(
                    "UPDATE affiliate_publishing_schedules SET board_name = 'Changed after activation' WHERE id = %s",
                    (schedule_id,),
                )
    with database.connection() as conn:
        job = conn.execute(
            "SELECT id, source_id, local_run_date FROM affiliate_pin_jobs WHERE schedule_id = %s ORDER BY id LIMIT 1",
            (schedule_id,),
        ).fetchone()
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE id = %s",
            (job["id"],),
        )
        conn.execute(
            """
            INSERT INTO affiliate_pin_jobs
                (schedule_id, source_id, run_at, local_run_date, daily_slot, idempotency_key)
            VALUES (%s, %s, now() - interval '30 seconds', %s, 2, %s)
            """,
            (schedule_id, job["source_id"], job["local_run_date"], f"phase9-second-job-{model2_db['suffix']}"),
        )

    workflow_started = Event()
    release_workflow = Event()
    observed = []

    def fake_workflow(payload, *, idempotency_key):
        observed.append((payload.niche_id, idempotency_key))
        workflow_started.set()
        assert release_workflow.wait(10), "test workflow release timed out"
        return {"published": False, "already_published": False, "product_id": None, "pin_id": None}

    monkeypatch.setattr(workflow, "publish_product_end_to_end", fake_workflow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(run_one_due_job)
        assert workflow_started.wait(10), "first worker did not claim a due job"
        second = run_one_due_job()
        release_workflow.set()
        first_result = first.result(timeout=15)

    assert first_result["status"] == "succeeded"
    assert observed and observed[0][0] == model2_db["niche_a"]
    assert second == {"claimed": False, "processed": False, "reason": "no_due_job"}


def test_model2_worker_retry_preserves_job_key_and_uncertain_result_is_quarantined(model2_db, monkeypatch):
    from fastapi import HTTPException
    from app import database, workflow
    from app.affiliate_scheduler import run_one_due_job

    schedule_id, _ = _create_and_activate_model2_schedule(model2_db["account_a"], model2_db["niche_a"])
    with database.connection() as conn:
        job = conn.execute(
            "SELECT id, idempotency_key FROM affiliate_pin_jobs WHERE schedule_id = %s ORDER BY id LIMIT 1",
            (schedule_id,),
        ).fetchone()
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE id = %s",
            (job["id"],),
        )

    workflow_calls = []
    def retry_once(payload, *, idempotency_key):
        workflow_calls.append((payload.niche_id, idempotency_key))
        if len(workflow_calls) == 1:
            raise HTTPException(status_code=503, detail="temporary test failure")
        return {"published": False, "already_published": False, "product_id": None, "pin_id": None}

    monkeypatch.setattr(workflow, "publish_product_end_to_end", retry_once)
    first = run_one_due_job()
    assert first["status"] == "retry_queued"
    with database.connection() as conn:
        stored = conn.execute(
            "SELECT status, idempotency_key FROM affiliate_pin_jobs WHERE id = %s",
            (job["id"],),
        ).fetchone()
        assert stored["status"] == "queued"
        assert stored["idempotency_key"] == job["idempotency_key"]
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE id = %s",
            (job["id"],),
        )
    second = run_one_due_job()
    assert second["status"] == "succeeded"
    assert len(workflow_calls) == 2
    assert workflow_calls[0] == workflow_calls[1]
    assert workflow_calls[0][0] == model2_db["niche_a"]

    # A separate due job with an ambiguous outcome becomes uncertain and is
    # never offered to the workflow again by a later worker invocation.
    next_id, _ = _create_and_activate_model2_schedule(model2_db["account_b"], model2_db["niche_b"])
    with database.connection() as conn:
        uncertain_job = conn.execute(
            "SELECT id FROM affiliate_pin_jobs WHERE schedule_id = %s ORDER BY id LIMIT 1",
            (next_id,),
        ).fetchone()
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE id = %s",
            (uncertain_job["id"],),
        )
    uncertain_calls = []
    def ambiguous(payload, *, idempotency_key):
        uncertain_calls.append(idempotency_key)
        raise HTTPException(status_code=409, detail="publish outcome uncertain")
    monkeypatch.setattr(workflow, "publish_product_end_to_end", ambiguous)
    uncertain_result = run_one_due_job()
    assert uncertain_result["status"] == "uncertain"
    assert run_one_due_job() == {"claimed": False, "processed": False, "reason": "no_due_job"}
    assert len(uncertain_calls) == 1
    with database.connection() as conn:
        state = conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s",
            (uncertain_job["id"],),
        ).fetchone()
    assert state["status"] == "uncertain"


def test_model2_workers_for_different_accounts_claim_independently(model2_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app import database, workflow
    from app.affiliate_scheduler import run_one_due_job

    schedule_a, _ = _create_and_activate_model2_schedule(model2_db["account_a"], model2_db["niche_a"])
    schedule_b, _ = _create_and_activate_model2_schedule(model2_db["account_b"], model2_db["niche_b"])
    with database.connection() as conn:
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE schedule_id IN (%s, %s)",
            (schedule_a, schedule_b),
        )

    both_in_workflow = Barrier(2)
    observed = []
    def concurrent_workflow(payload, *, idempotency_key):
        observed.append((payload.account_id, payload.niche_id))
        both_in_workflow.wait(timeout=10)
        return {"published": False, "already_published": False, "product_id": None, "pin_id": None}

    monkeypatch.setattr(workflow, "publish_product_end_to_end", concurrent_workflow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_one_due_job), pool.submit(run_one_due_job)]
        results = [future.result(timeout=15) for future in futures]

    assert all(result["status"] == "succeeded" for result in results)
    assert set(observed) == {
        (model2_db["account_a"], model2_db["niche_a"]),
        (model2_db["account_b"], model2_db["niche_b"]),
    }



def test_model2_uncertain_job_consumes_daily_quota_and_blocks_schedule_replacement(model2_db, monkeypatch):
    from fastapi import HTTPException
    from app import database, workflow
    from app.affiliate_scheduler import (
        activate_schedule,
        create_draft_schedule,
        run_one_due_job,
    )

    old_id, _ = _create_and_activate_model2_schedule(
        model2_db["account_a"], model2_db["niche_a"], daily_limit=1
    )
    with database.connection() as conn:
        first = conn.execute(
            "SELECT id, source_id, local_run_date FROM affiliate_pin_jobs WHERE schedule_id = %s ORDER BY id LIMIT 1",
            (old_id,),
        ).fetchone()
        conn.execute(
            "UPDATE affiliate_pin_jobs SET run_at = now() - interval '1 minute' WHERE id = %s",
            (first["id"],),
        )
        conn.execute(
            """
            INSERT INTO affiliate_pin_jobs
                (schedule_id, source_id, run_at, local_run_date, daily_slot, idempotency_key)
            VALUES (%s, %s, now() - interval '30 seconds', %s, 2, %s)
            """,
            (old_id, first["source_id"], first["local_run_date"], f"phase9-uncertain-quota-{model2_db['suffix']}"),
        )

    calls = []
    def ambiguous(payload, *, idempotency_key):
        calls.append(idempotency_key)
        raise HTTPException(status_code=409, detail="publish outcome uncertain")
    monkeypatch.setattr(workflow, "publish_product_end_to_end", ambiguous)

    result = run_one_due_job()
    assert result["status"] == "uncertain"
    # Uncertain is a terminal scheduler state, but it may represent a real Pin.
    # It must consume today's account quota and cannot be replayed by another job.
    assert run_one_due_job() == {"claimed": False, "processed": False, "reason": "no_due_job"}
    assert len(calls) == 1

    # Even on a later local day, unresolved uncertainty blocks replacing the
    # old schedule until an operator reconciles the publication outcome.
    new_draft = create_draft_schedule(_model2_schedule_payload(model2_db["account_a"], model2_db["niche_a"]))
    with pytest.raises(HTTPException) as blocked:
        activate_schedule(new_draft["schedule_id"])
    assert blocked.value.status_code == 409
    assert "uncertain" in blocked.value.detail.casefold()


def _create_uncertain_scheduler_fixture(
    conn, *, account_id: str, niche_id: int, suffix: str,
    publication_status: str | None = "unknown",
    publication_account_id: str | None = None,
    attribution_niche_id: int | None = None,
    pending_age_minutes: int | None = None,
) -> tuple[int, int | None]:
    schedule_id = conn.execute(
        """
        INSERT INTO affiliate_publishing_schedules
            (account_id, niche_id, timezone, starts_on, ends_on,
             daily_pin_limit, board_name, status)
        VALUES (%s, %s, 'UTC', CURRENT_DATE, CURRENT_DATE + 1, 2,
                'Test Board', 'active')
        RETURNING id
        """,
        (account_id, niche_id),
    ).fetchone()["id"]
    source_id = conn.execute(
        """
        INSERT INTO affiliate_product_sources
            (schedule_id, product_name, product_details, affiliate_url)
        VALUES (%s, 'Synthetic product', 'Synthetic test fixture',
                'https://example.invalid/affiliate')
        RETURNING id
        """,
        (schedule_id,),
    ).fetchone()["id"]
    key = f"reconcile-test-{suffix}-idempotency"
    job_id = conn.execute(
        """
        INSERT INTO affiliate_pin_jobs
            (schedule_id, source_id, run_at, local_run_date, daily_slot,
             idempotency_key, status, attempt_count)
        VALUES (%s, %s, now(), CURRENT_DATE, 1, %s, 'uncertain', 1)
        RETURNING id
        """,
        (schedule_id, source_id, key),
    ).fetchone()["id"]

    publication_id = None
    if publication_status is not None:
        product_id = conn.execute(
            """
            INSERT INTO products
                (product_name, product_details, image_url, affiliate_url, idempotency_key)
            VALUES (%s, 'Synthetic test fixture', 'https://example.invalid/image.png',
                    'https://example.invalid/affiliate', %s)
            RETURNING id
            """,
            (f"Reconciliation fixture {suffix}", key),
        ).fetchone()["id"]
        content_id = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, 1, 'test', 'test', 'test', 'test', 'test', 'test', 'test')
            RETURNING id
            """,
            (product_id,),
        ).fetchone()["id"]
        publication_account_id = publication_account_id or account_id
        age_sql = "now() - (%s * interval '1 minute')" if pending_age_minutes is not None else "now()"
        params = [product_id, content_id, f"test-board-{suffix}", publication_account_id, publication_status]
        if pending_age_minutes is not None:
            params.append(pending_age_minutes)
        publication_id = conn.execute(
            f"""
            INSERT INTO pin_publications
                (product_id, content_version_id, board_id, account_id, status, updated_at)
            VALUES (%s, %s, %s, %s, %s, {age_sql})
            RETURNING id
            """,
            tuple(params),
        ).fetchone()["id"]
        if attribution_niche_id is not None:
            conn.execute(
                """
                INSERT INTO model2_publication_niche_attributions
                    (publication_id, account_id, niche_id, attribution_source)
                VALUES (%s, %s, %s, 'workflow')
                """,
                (publication_id, publication_account_id, attribution_niche_id),
            )
    return job_id, publication_id


def test_scheduler_reconciliation_atomically_marks_unknown_publication_succeeded(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=model2_db["suffix"], attribution_niche_id=model2_db["niche_a"],
        )

    result = database.reconcile_scheduler_job(
        job_id, account_id=model2_db["account_a"], outcome="succeeded",
        pinterest_pin_id=f"synthetic-pin-{model2_db['suffix']}",
        operator_evidence="Verified synthetic fixture in the test evidence record.",
    )
    assert result["status"] == "succeeded"
    assert result["publication_id"] == publication_id
    with database.connection() as conn:
        publication = conn.execute(
            "SELECT status, pinterest_pin_id FROM pin_publications WHERE id = %s",
            (publication_id,),
        ).fetchone()
        job = conn.execute(
            "SELECT status, pinterest_pin_id FROM affiliate_pin_jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
        audit = conn.execute(
            "SELECT outcome, publication_id FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    assert publication == {
        "status": "succeeded", "pinterest_pin_id": f"synthetic-pin-{model2_db['suffix']}"
    }
    assert job == {
        "status": "succeeded", "pinterest_pin_id": f"synthetic-pin-{model2_db['suffix']}"
    }
    assert audit == {"outcome": "succeeded", "publication_id": publication_id}
    assert result["read_only"] is False


def test_scheduler_reconciliation_can_fail_job_without_publication_only_with_absence_confirmation(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"no-ledger-{model2_db['suffix']}", publication_status=None,
        )
    with pytest.raises(ValueError, match="confirm_pin_absent"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="failed",
            pinterest_pin_id=None,
            operator_evidence="Operator checked the account board and confirmed absence.",
        )
    result = database.reconcile_scheduler_job(
        job_id, account_id=model2_db["account_a"], outcome="failed",
        pinterest_pin_id=None,
        operator_evidence="Operator checked the account board and confirmed absence.",
        confirm_pin_absent=True,
    )
    assert result["status"] == "failed"
    assert result["publication_id"] is None
    with database.connection() as conn:
        audit = conn.execute(
            "SELECT publication_id, outcome FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    assert audit == {"publication_id": None, "outcome": "failed"}


def test_scheduler_reconciliation_rejects_recent_pending_publication(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"pending-{model2_db['suffix']}", publication_status="pending",
            pending_age_minutes=2, attribution_niche_id=model2_db["niche_a"],
        )
    with pytest.raises(ValueError, match="10 minutes"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-pending",
            operator_evidence="Synthetic evidence for a pending publication.",
        )
    with database.connection() as conn:
        status = conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s", (job_id,)
        ).fetchone()["status"]
        audit_count = conn.execute(
            "SELECT count(*) AS n FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()["n"]
    assert status == "uncertain"
    assert audit_count == 0


def test_scheduler_reconciliation_rejects_account_mismatch(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"mismatch-{model2_db['suffix']}",
            publication_account_id=model2_db["account_b"],
        )
    with pytest.raises(ValueError, match="publication account"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-mismatch",
            operator_evidence="Synthetic evidence for account mismatch validation.",
        )


def test_scheduler_reconciliation_rejects_missing_model2_publication_attribution(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"no-attribution-{model2_db['suffix']}",
        )
    with pytest.raises(ValueError, match="attribution"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-no-attribution",
            operator_evidence="Synthetic evidence for missing niche attribution.",
        )


def test_scheduler_reconciliation_is_single_use_and_does_not_requeue(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"single-use-{model2_db['suffix']}", publication_status=None,
        )
    kwargs = dict(
        account_id=model2_db["account_a"], outcome="failed", pinterest_pin_id=None,
        operator_evidence="Operator confirmed the synthetic Pin is absent.",
        confirm_pin_absent=True,
    )
    database.reconcile_scheduler_job(job_id, **kwargs)
    with pytest.raises(ValueError, match="only uncertain"):
        database.reconcile_scheduler_job(job_id, **kwargs)
    with database.connection() as conn:
        audit_count = conn.execute(
            "SELECT count(*) AS n FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()["n"]
        job_status = conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s", (job_id,)
        ).fetchone()["status"]
    assert audit_count == 1
    assert job_status == "failed"



def test_scheduler_reconciliation_rejects_success_without_publication_ledger(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"no-ledger-success-{model2_db['suffix']}", publication_status=None,
        )
    with pytest.raises(ValueError, match="no publication ledger"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-unproven",
            operator_evidence="Synthetic evidence cannot replace missing ledger linkage.",
        )
    with database.connection() as conn:
        assert conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s", (job_id,)
        ).fetchone()["status"] == "uncertain"


def test_scheduler_reconciliation_rejects_multiple_publication_candidates(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"multi-{model2_db['suffix']}", attribution_niche_id=model2_db["niche_a"],
        )
        base = conn.execute(
            "SELECT product_id FROM pin_publications WHERE id = %s", (publication_id,)
        ).fetchone()
        content_id = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, 2, 'test', 'test', 'test', 'test', 'test', 'test', 'test')
            RETURNING id
            """,
            (base["product_id"],),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO pin_publications
                (product_id, content_version_id, board_id, account_id, status)
            VALUES (%s, %s, %s, %s, 'unknown')
            """,
            (base["product_id"], content_id, f"second-board-{model2_db['suffix']}", model2_db["account_a"]),
        )
    with pytest.raises(ValueError, match="multiple publication candidates"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-ambiguous",
            operator_evidence="Synthetic evidence for ambiguous publication linkage.",
        )


def test_scheduler_reconciliation_rejects_wrong_model2_niche_attribution(model2_db):
    with database.connection() as conn:
        conn.execute(
            """
            INSERT INTO model2_account_niches (account_id, niche_id, is_primary)
            VALUES (%s, %s, FALSE)
            """,
            (model2_db["account_a"], model2_db["niche_b"]),
        )
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"wrong-niche-{model2_db['suffix']}",
            attribution_niche_id=model2_db["niche_b"],
        )
    with pytest.raises(ValueError, match="mismatched"):
        database.reconcile_scheduler_job(
            job_id, account_id=model2_db["account_a"], outcome="succeeded",
            pinterest_pin_id="synthetic-pin-wrong-niche",
            operator_evidence="Synthetic evidence for mismatched niche attribution.",
        )


def test_scheduler_reconciliation_accepts_stale_pending_publication(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"stale-pending-{model2_db['suffix']}",
            publication_status="pending", pending_age_minutes=15,
            attribution_niche_id=model2_db["niche_a"],
        )
    result = database.reconcile_scheduler_job(
        job_id, account_id=model2_db["account_a"], outcome="succeeded",
        pinterest_pin_id="synthetic-pin-stale-pending",
        operator_evidence="Synthetic evidence for a pending record older than ten minutes.",
    )
    assert result["status"] == "succeeded"
    with database.connection() as conn:
        assert conn.execute(
            "SELECT status FROM pin_publications WHERE id = %s", (publication_id,)
        ).fetchone()["status"] == "succeeded"


def test_scheduler_reconciliation_supports_legacy_model1_job_without_niche_attribution(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=None,
            suffix=f"legacy-{model2_db['suffix']}",
            attribution_niche_id=None,
        )
    result = database.reconcile_scheduler_job(
        job_id, account_id=model2_db["account_a"], outcome="succeeded",
        pinterest_pin_id="synthetic-pin-legacy",
        operator_evidence="Synthetic evidence for legacy Model 1 publication linkage.",
    )
    assert result["status"] == "succeeded"
    assert result["publication_id"] == publication_id


def test_scheduler_reconciliation_rolls_back_ledger_and_audit_if_job_update_fails(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"rollback-{model2_db['suffix']}",
            attribution_niche_id=model2_db["niche_a"],
        )
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION test_abort_scheduler_job_reconcile()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'synthetic scheduler update failure';
            END;
            $$
            """
        )
        conn.execute(
            """
            CREATE TRIGGER test_abort_scheduler_job_reconcile
            BEFORE UPDATE ON affiliate_pin_jobs
            FOR EACH ROW EXECUTE FUNCTION test_abort_scheduler_job_reconcile()
            """
        )
    try:
        with pytest.raises(RaiseException, match="synthetic scheduler update failure"):
            database.reconcile_scheduler_job(
                job_id, account_id=model2_db["account_a"], outcome="succeeded",
                pinterest_pin_id="synthetic-pin-rollback",
                operator_evidence="Synthetic evidence used to verify atomic rollback.",
            )
    finally:
        with database.connection() as conn:
            conn.execute("DROP TRIGGER IF EXISTS test_abort_scheduler_job_reconcile ON affiliate_pin_jobs")
            conn.execute("DROP FUNCTION IF EXISTS test_abort_scheduler_job_reconcile()")
    with database.connection() as conn:
        publication_status = conn.execute(
            "SELECT status FROM pin_publications WHERE id = %s", (publication_id,)
        ).fetchone()["status"]
        job_status = conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s", (job_id,)
        ).fetchone()["status"]
        audit_count = conn.execute(
            "SELECT count(*) AS n FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()["n"]
    assert publication_status == "unknown"
    assert job_status == "uncertain"
    assert audit_count == 0


def test_scheduler_reconciliation_audit_is_immutable(model2_db):
    with database.connection() as conn:
        job_id, _ = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"audit-immutable-{model2_db['suffix']}", publication_status=None,
        )
    database.reconcile_scheduler_job(
        job_id, account_id=model2_db["account_a"], outcome="failed",
        pinterest_pin_id=None,
        operator_evidence="Operator confirmed the synthetic Pin is absent.",
        confirm_pin_absent=True,
    )
    with database.connection() as conn:
        with conn.transaction():
            with pytest.raises(RaiseException, match="append-only"):
                with conn.transaction():
                    conn.execute(
                        "UPDATE affiliate_job_reconciliation_audit SET outcome = 'succeeded' WHERE job_id = %s",
                        (job_id,),
                    )



def test_scheduler_reconciliation_inspection_is_read_only_and_account_scoped(model2_db):
    with database.connection() as conn:
        job_id, publication_id = _create_uncertain_scheduler_fixture(
            conn, account_id=model2_db["account_a"], niche_id=model2_db["niche_a"],
            suffix=f"inspect-{model2_db['suffix']}",
            attribution_niche_id=model2_db["niche_a"],
        )
    result = database.get_scheduler_job_reconciliation(
        job_id, account_id=model2_db["account_a"],
    )
    assert result["job_status"] == "uncertain"
    assert result["linkage_status"] == "matched"
    assert result["publication_candidate_count"] == 1
    assert result["publication"]["publication_id"] == publication_id
    assert result["read_only"] is True
    assert "publication_account_id" not in result["publication"]
    assert database.get_scheduler_job_reconciliation(
        job_id, account_id=model2_db["account_b"],
    ) is None
    with database.connection() as conn:
        job_status = conn.execute(
            "SELECT status FROM affiliate_pin_jobs WHERE id = %s", (job_id,)
        ).fetchone()["status"]
        audit_count = conn.execute(
            "SELECT count(*) AS n FROM affiliate_job_reconciliation_audit WHERE job_id = %s",
            (job_id,),
        ).fetchone()["n"]
    assert job_status == "uncertain"
    assert audit_count == 0
