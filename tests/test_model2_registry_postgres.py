"""Disposable-PostgreSQL tests for the additive Model 2 registry migration."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from app import database
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
    niche_a = f"test-niche-a-{suffix}"
    niche_b = f"test-niche-b-{suffix}"
    try:
        with database.connection() as conn:
            conn.execute(
                """
                INSERT INTO pinterest_credentials
                    (account_id, pinterest_user_id, access_token_ciphertext, status)
                VALUES (%s, %s, %s, 'connected'), (%s, %s, %s, 'connected')
                """,
                (account_a, "test-user-a", b"test-ciphertext-a",
                 account_b, "test-user-b", b"test-ciphertext-b"),
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
                "DELETE FROM model2_account_niches WHERE account_id IN (%s, %s)",
                (account_a, account_b),
            )
            conn.execute(
                "DELETE FROM model2_account_profiles WHERE account_id IN (%s, %s)",
                (account_a, account_b),
            )
            conn.execute(
                "DELETE FROM pinterest_credentials WHERE account_id IN (%s, %s)",
                (account_a, account_b),
            )
            conn.execute(
                "DELETE FROM model2_niches WHERE slug IN (%s, %s)",
                (niche_a, niche_b),
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

        with conn.transaction():
            with pytest.raises(ForeignKeyViolation):
                with conn.transaction():
                    conn.execute(
                        """
                        INSERT INTO model2_account_niches (account_id, niche_id, is_primary)
                        VALUES (%s, %s, FALSE)
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
                        "SELECT pg_backend_pid() AS pid"
                    ).fetchone()["pid"]
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
                SELECT cardinality(pg_blocking_pids(pid)) AS blocker_count
                FROM pg_stat_activity
                WHERE pid = %s
                """,
                (outcomes["second_pid"],),
            ).fetchone()
        if wait_state and wait_state["blocker_count"] > 0:
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
