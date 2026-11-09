"""Synthetic populated legacy Model 1 database upgrade rehearsal.

This test creates a separate disposable PostgreSQL database, applies migrations
001-013, inserts legacy scheduler rows, then applies migrations 014-015. It never
connects to DATABASE_URL or any remote/production database.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def _disposable_ci_urls() -> tuple[str, str]:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    assert raw, "TEST_DATABASE_URL is required; never fall back to DATABASE_URL"
    parsed = urlsplit(raw)
    assert parsed.scheme in {"postgres", "postgresql"}
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    assert parsed.port == 5432
    assert parsed.username == "postgres"
    assert parsed.path == "/model2_test"
    admin = urlunsplit((parsed.scheme, parsed.netloc, "/postgres", parsed.query, parsed.fragment))
    return raw, admin


def test_populated_legacy_model1_scheduler_survives_model2_migrations():
    _, admin_dsn = _disposable_ci_urls()
    database_name = f"model2_legacy_upgrade_{uuid4().hex[:12]}"
    created = False
    try:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
        created = True

        parsed = urlsplit(admin_dsn)
        upgrade_dsn = urlunsplit(
            (parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment)
        )
        with psycopg.connect(upgrade_dsn) as conn:
            conn.execute(
                """
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            legacy_migrations = sorted(
                path for path in MIGRATIONS.glob("[0-9]*.sql")
                if path.name[:3].isdigit() and int(path.name[:3]) <= 13
            )
            assert len(legacy_migrations) == 13
            for migration in legacy_migrations:
                conn.execute(migration.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration.name,),
                )

            schedule = conn.execute(
                """
                INSERT INTO affiliate_publishing_schedules
                    (account_id, timezone, starts_on, ends_on, daily_pin_limit,
                     board_name, board_description, status)
                VALUES
                    ('legacy-account-001', 'UTC', DATE '2026-01-01',
                     DATE '2026-01-30', 5, 'Legacy Home Board',
                     'Existing Model 1 schedule', 'active')
                RETURNING id
                """
            ).fetchone()
            schedule_id = schedule[0]
            source = conn.execute(
                """
                INSERT INTO affiliate_product_sources
                    (schedule_id, product_name, product_details, affiliate_url)
                VALUES (%s, 'Legacy organizer', 'Existing Model 1 source',
                        'https://example.com/legacy-product')
                RETURNING id
                """,
                (schedule_id,),
            ).fetchone()
            source_id = source[0]
            conn.execute(
                """
                INSERT INTO affiliate_pin_jobs
                    (schedule_id, source_id, run_at, local_run_date, daily_slot,
                     idempotency_key, status)
                VALUES (%s, %s, TIMESTAMPTZ '2026-01-02 09:00:00+00',
                        DATE '2026-01-02', 1, 'legacy-upgrade-job-001', 'queued')
                """,
                (schedule_id, source_id),
            )

            for migration_name in (
                "014_model2_account_aware_scheduling.sql",
                "015_affiliate_job_reconciliation_audit.sql",
            ):
                migration = MIGRATIONS / migration_name
                conn.execute(migration.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration_name,),
                )

            schedule_after = conn.execute(
                """
                SELECT account_id, niche_id, status, board_name, board_description
                FROM affiliate_publishing_schedules WHERE id = %s
                """,
                (schedule_id,),
            ).fetchone()
            job_after = conn.execute(
                """
                SELECT status, idempotency_key, product_id, pinterest_pin_id
                FROM affiliate_pin_jobs WHERE schedule_id = %s
                """,
                (schedule_id,),
            ).fetchone()
            assert schedule_after == (
                "legacy-account-001", None, "active", "Legacy Home Board",
                "Existing Model 1 schedule",
            )
            assert job_after == ("queued", "legacy-upgrade-job-001", None, None)

            # Migration 014's guard must preserve legacy Model 1 update semantics.
            conn.execute(
                "UPDATE affiliate_publishing_schedules SET board_name = %s WHERE id = %s",
                ("Updated Legacy Board", schedule_id),
            )
            assert conn.execute(
                "SELECT board_name FROM affiliate_publishing_schedules WHERE id = %s",
                (schedule_id,),
            ).fetchone()[0] == "Updated Legacy Board"

            indexes = {
                row[0] for row in conn.execute(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
                ).fetchall()
            }
            assert "affiliate_one_active_schedule_per_account_idx" in indexes
            assert conn.execute(
                "SELECT count(*) FROM schema_migrations"
            ).fetchone()[0] == 15
    finally:
        if created:
            with psycopg.connect(admin_dsn, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
                )
