"""Disposable PostgreSQL custom-format backup/restore rehearsal.

This test creates source and restore databases only inside the GitHub Actions
loopback PostgreSQL service. It never reads DATABASE_URL or contacts Neon.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def _disposable_admin_dsn() -> str:
    raw = os.environ.get("TEST_DATABASE_URL", "")
    assert raw, "TEST_DATABASE_URL is required; never fall back to DATABASE_URL"
    parsed = urlsplit(raw)
    assert parsed.scheme in {"postgres", "postgresql"}
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    assert parsed.port == 5432
    assert parsed.username == "postgres"
    assert parsed.path == "/model2_test"
    return urlunsplit((parsed.scheme, parsed.netloc, "/postgres", parsed.query, parsed.fragment))


def _database_dsn(admin_dsn: str, name: str) -> str:
    parsed = urlsplit(admin_dsn)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{name}", parsed.query, parsed.fragment))


def _create_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


def _drop_database(admin_dsn: str, name: str) -> None:
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def test_custom_format_backup_restores_migrated_schema_and_legacy_rows():
    admin_dsn = _disposable_admin_dsn()
    suffix = uuid4().hex[:12]
    source_name = f"model2_backup_source_{suffix}"
    restore_name = f"model2_backup_restore_{suffix}"
    created: list[str] = []
    try:
        _create_database(admin_dsn, source_name)
        created.append(source_name)
        source_dsn = _database_dsn(admin_dsn, source_name)

        with psycopg.connect(source_dsn) as conn:
            conn.execute(
                """
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            migrations = sorted(MIGRATIONS.glob("[0-9]*.sql"))
            assert len(migrations) == 16
            for migration in migrations:
                conn.execute(migration.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration.name,),
                )

            schedule_id = conn.execute(
                """
                INSERT INTO affiliate_publishing_schedules
                    (account_id, timezone, starts_on, ends_on, daily_pin_limit,
                     board_name, board_description, status)
                VALUES
                    ('legacy-backup-account', 'UTC', DATE '2026-01-01',
                     DATE '2026-01-30', 5, 'Legacy Backup Board',
                     'Synthetic backup fixture', 'active')
                RETURNING id
                """
            ).fetchone()[0]
            source_id = conn.execute(
                """
                INSERT INTO affiliate_product_sources
                    (schedule_id, product_name, product_details, affiliate_url)
                VALUES (%s, 'Backup fixture product', 'Synthetic legacy source',
                        'https://example.com/backup-fixture')
                RETURNING id
                """,
                (schedule_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO affiliate_pin_jobs
                    (schedule_id, source_id, run_at, local_run_date, daily_slot,
                     idempotency_key, status)
                VALUES (%s, %s, TIMESTAMPTZ '2026-01-02 09:00:00+00',
                        DATE '2026-01-02', 1, 'backup-restore-fixture-job', 'queued')
                """,
                (schedule_id, source_id),
            )

        _create_database(admin_dsn, restore_name)
        created.append(restore_name)
        restore_dsn = _database_dsn(admin_dsn, restore_name)

        with tempfile.TemporaryDirectory(prefix="model2-pg-backup-") as temp_dir:
            archive = Path(temp_dir) / "model2.dump"
            # Use the same PostgreSQL 16 image as the disposable server. A
            # newer host pg_restore may emit SET parameters unsupported by PG16.
            subprocess.run(
                ["docker", "run", "--rm", "--network", "host",
                 "--volume", f"{temp_dir}:/backup",
                 "--env", "PGPASSWORD=model2-ci-only",
                 "postgres:16", "pg_dump", "--format=custom", "--no-owner",
                 "--no-privileges", "--file", "/backup/model2.dump",
                 "--dbname", source_dsn],
                check=True, capture_output=True, text=True, timeout=120,
            )
            assert archive.is_file() and archive.stat().st_size > 0
            subprocess.run(
                ["docker", "run", "--rm", "--network", "host",
                 "--volume", f"{temp_dir}:/backup",
                 "--env", "PGPASSWORD=model2-ci-only",
                 "postgres:16", "pg_restore", "--exit-on-error", "--no-owner",
                 "--no-privileges", "--dbname", restore_dsn, "/backup/model2.dump"],
                check=True, capture_output=True, text=True, timeout=120,
            )

        with psycopg.connect(restore_dsn) as restored:
            versions = [
                row[0] for row in restored.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ]
            assert versions == [migration.name for migration in sorted(MIGRATIONS.glob("[0-9]*.sql"))]
            schedule = restored.execute(
                """
                SELECT account_id, niche_id, status, board_name
                FROM affiliate_publishing_schedules
                WHERE account_id = 'legacy-backup-account'
                """
            ).fetchone()
            assert schedule == ("legacy-backup-account", None, "active", "Legacy Backup Board")
            job = restored.execute(
                """
                SELECT status, idempotency_key
                FROM affiliate_pin_jobs
                WHERE idempotency_key = 'backup-restore-fixture-job'
                """
            ).fetchone()
            assert job == ("queued", "backup-restore-fixture-job")
            assert restored.execute(
                """
                SELECT count(*) FROM pg_trigger
                WHERE tgname IN (
                    'affiliate_schedule_immutability_guard',
                    'affiliate_job_reconciliation_audit_no_mutation',
                    'affiliate_job_reconciliation_audit_no_truncate'
                ) AND NOT tgisinternal
                """
            ).fetchone()[0] == 3
    finally:
        for name in reversed(created):
            _drop_database(admin_dsn, name)
