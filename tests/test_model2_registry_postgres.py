"""Disposable-PostgreSQL tests for the additive Model 2 registry migration."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from app import database
from app.model2_domain import AccountNicheAssignmentInput, AccountProfileInput, NicheInput
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
                "DELETE FROM pin_publications WHERE account_id IN (%s, %s) AND board_id LIKE %s",
                (account_a, account_b, f"test-board-{suffix}%"),
            )
            conn.execute(
                "DELETE FROM content_versions WHERE product_id IN "
                "(SELECT id FROM products WHERE product_name LIKE %s)",
                (f"Model2 test product {suffix}%",),
            )
            conn.execute(
                "DELETE FROM products WHERE product_name LIKE %s",
                (f"Model2 test product {suffix}%",),
            )
            conn.execute(
                "DELETE FROM model2_learning_snapshots WHERE account_id IN (%s, %s)",
                (account_a, account_b),
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
