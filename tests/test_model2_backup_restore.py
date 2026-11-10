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
            assert len(migrations) == 18
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


def test_pre_model2_backup_restores_legacy_schema_after_upgrade_rollback():
    """Recover a compatible legacy schema from a synthetic pre-upgrade backup."""
    admin_dsn = _disposable_admin_dsn()
    suffix = uuid4().hex[:12]
    source_name = f"model2_rollback_source_{suffix}"
    recovery_name = f"model2_rollback_recovery_{suffix}"
    created: list[str] = []
    try:
        _create_database(admin_dsn, source_name)
        created.append(source_name)
        source_dsn = _database_dsn(admin_dsn, source_name)
        with psycopg.connect(source_dsn) as conn:
            conn.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            legacy_migrations = sorted(path for path in MIGRATIONS.glob("[0-9]*.sql") if path.name[:3].isdigit() and int(path.name[:3]) <= 12)
            assert len(legacy_migrations) == 13
            for migration in legacy_migrations:
                conn.execute(migration.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
            schedule_id = conn.execute("""INSERT INTO affiliate_publishing_schedules
                (account_id, timezone, starts_on, ends_on, daily_pin_limit, board_name, board_description, status)
                VALUES ('rollback-legacy-account', 'UTC', DATE '2026-01-01', DATE '2026-01-30', 5,
                        'Pre-Model2 Board', 'Synthetic pre-upgrade schedule', 'active') RETURNING id""").fetchone()[0]
            source_id = conn.execute("""INSERT INTO affiliate_product_sources
                (schedule_id, product_name, product_details, affiliate_url)
                VALUES (%s, 'Pre-upgrade product', 'Synthetic legacy source', 'https://example.com/pre-upgrade')
                RETURNING id""", (schedule_id,)).fetchone()[0]
            conn.execute("""INSERT INTO affiliate_pin_jobs
                (schedule_id, source_id, run_at, local_run_date, daily_slot, idempotency_key, status)
                VALUES (%s, %s, TIMESTAMPTZ '2026-01-02 09:00:00+00', DATE '2026-01-02', 1,
                        'pre-model2-rollback-job', 'queued')""", (schedule_id, source_id))

        _create_database(admin_dsn, recovery_name)
        created.append(recovery_name)
        recovery_dsn = _database_dsn(admin_dsn, recovery_name)
        with tempfile.TemporaryDirectory(prefix="model2-rollback-backup-") as temp_dir:
            archive = Path(temp_dir) / "pre-model2.dump"
            docker_prefix = ["docker", "run", "--rm", "--network", "host", "--volume", f"{temp_dir}:/backup", "--env", "PGPASSWORD=model2-ci-only", "postgres:16"]
            subprocess.run(docker_prefix + ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", "/backup/pre-model2.dump", "--dbname", source_dsn], check=True, capture_output=True, text=True, timeout=120)
            assert archive.is_file() and archive.stat().st_size > 0
            with psycopg.connect(source_dsn) as upgraded:
                model2_migrations = sorted(path for path in MIGRATIONS.glob("[0-9]*.sql") if path.name[:3].isdigit() and int(path.name[:3]) >= 13)
                assert len(model2_migrations) == 5
                for migration in model2_migrations:
                    upgraded.execute(migration.read_text(encoding="utf-8"))
                    upgraded.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration.name,))
                assert upgraded.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 18
                assert upgraded.execute("""SELECT count(*) FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'affiliate_publishing_schedules'
                    AND column_name = 'niche_id'""").fetchone()[0] == 1
            subprocess.run(docker_prefix + ["pg_restore", "--exit-on-error", "--no-owner", "--no-privileges", "--dbname", recovery_dsn, "/backup/pre-model2.dump"], check=True, capture_output=True, text=True, timeout=120)

        with psycopg.connect(recovery_dsn) as recovered:
            assert [row[0] for row in recovered.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()] == [migration.name for migration in legacy_migrations]
            assert recovered.execute("""SELECT count(*) FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'affiliate_publishing_schedules'
                AND column_name = 'niche_id'""").fetchone()[0] == 0
            assert recovered.execute("""SELECT count(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name IN
                ('model2_niches', 'model2_account_profiles', 'model2_account_niches', 'affiliate_job_reconciliation_audit', 'pinterest_board_operations', 'pinterest_refresh_operations')""").fetchone()[0] == 0
            assert recovered.execute("""SELECT account_id, status, board_name, board_description
                FROM affiliate_publishing_schedules WHERE account_id = 'rollback-legacy-account'""").fetchone() == (
                    "rollback-legacy-account", "active", "Pre-Model2 Board", "Synthetic pre-upgrade schedule")
            assert recovered.execute("""SELECT status, idempotency_key FROM affiliate_pin_jobs
                WHERE idempotency_key = 'pre-model2-rollback-job'""").fetchone() == ("queued", "pre-model2-rollback-job")
    finally:
        for name in reversed(created):
            _drop_database(admin_dsn, name)
