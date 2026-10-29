"""Opt-in integration test for pooled-connection recovery after backend loss.

Run only against the dedicated disposable Neon test branch:
PB10_TEST_DATABASE_URL=... pytest -q tests/test_database_pool_recovery_integration.py

This test terminates one backend session; it must never point at production.
"""
import os
import time
from urllib.parse import parse_qsl, urlsplit

import psycopg
import pytest
from psycopg_pool import ConnectionPool

_DISPOSABLE_HOST = "ep-ancient-cherry-arpqssmi-pooler.c-4.us-west-2.aws.neon.tech"


def _is_dedicated_disposable_uri(conninfo: str) -> bool:
    """Accept only the dedicated single-host URI without routing overrides."""
    try:
        parsed = urlsplit(conninfo)
        query = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return False
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        return False
    if parsed.username is None or parsed.path != "/pinterest_affiliate":
        return False
    # libpq URI authorities support multiple comma-separated hosts. urlsplit()
    # exposes only the first as .hostname, so reject such authorities entirely.
    authority_without_userinfo = parsed.netloc.rsplit("@", 1)[-1]
    if "," in authority_without_userinfo or authority_without_userinfo.startswith("["):
        return False
    if parsed.hostname.lower() != _DISPOSABLE_HOST:
        return False
    forbidden = {"host", "hostaddr", "port", "dbname", "service", "servicefile", "options"}
    allowed = {"sslmode", "channel_binding", "application_name", "connect_timeout"}
    if any(key.lower() in forbidden for key, _ in query):
        return False
    return not any(key.lower() not in allowed for key, _ in query)


def test_disposable_url_guard_rejects_dsn_routing_and_multi_host_bypasses():
    assert not _is_dedicated_disposable_uri(
        "host=prod.db.example dbname=pb10-test user=test password=not-a-real-secret"
    )
    assert not _is_dedicated_disposable_uri(
        "postgresql://test@prod.db.example/pinterest_affiliate"
    )
    assert not _is_dedicated_disposable_uri(
        "postgresql://test@ep-ancient-cherry-arpqssmi-pooler.c-4.us-west-2.aws.neon.tech,prod.db.example/pinterest_affiliate"
    )
    assert not _is_dedicated_disposable_uri(
        "postgresql://test@ep-ancient-cherry-arpqssmi-pooler.c-4.us-west-2.aws.neon.tech/pinterest_affiliate?host=prod.db.example"
    )
    assert not _is_dedicated_disposable_uri(
        "postgresql://test@ep-ancient-cherry-arpqssmi-pooler.c-4.us-west-2.aws.neon.tech/pinterest_affiliate?dbname=production"
    )
    assert _is_dedicated_disposable_uri(
        "postgresql://test:masked@ep-ancient-cherry-arpqssmi-pooler.c-4.us-west-2.aws.neon.tech/pinterest_affiliate?sslmode=require"
    )


def test_pool_replaces_backend_terminated_on_disposable_test_branch():
    conninfo = os.getenv("PB10_TEST_DATABASE_URL")
    if not conninfo:
        pytest.skip("PB10_TEST_DATABASE_URL is not configured")
    if not _is_dedicated_disposable_uri(conninfo):
        pytest.skip("PB10_TEST_DATABASE_URL must use the exact dedicated single-host Neon URI and expected database")

    def check_connection(conn):
        conn.execute("")

    pool = ConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=2,
        timeout=10,
        check=check_connection,
        open=True,
    )
    try:
        pool.wait(timeout=20)
        with pool.connection() as conn:
            stale_pid = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
            assert conn.execute("SELECT 1").fetchone()[0] == 1

        admin = psycopg.connect(conninfo, autocommit=True)
        try:
            try:
                terminated = admin.execute(
                    "SELECT pg_terminate_backend(%s)", (stale_pid,)
                ).fetchone()[0]
            except psycopg.errors.AdminShutdown:
                terminated = True
        finally:
            try:
                admin.close()
            except Exception:
                pass
        assert terminated is True

        replacement_pid = None
        last_error = None
        for _ in range(8):
            try:
                with pool.connection(timeout=5) as conn:
                    replacement_pid = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
                    assert conn.execute("SELECT 1").fetchone()[0] == 1
                break
            except Exception as exc:
                last_error = type(exc).__name__
                time.sleep(0.25)

        assert replacement_pid is not None, f"Pool did not recover; last exception={last_error}"
        assert replacement_pid != stale_pid
    finally:
        pool.close()
