"""Opt-in integration test for pooled-connection recovery after backend loss.

Run only against a disposable PostgreSQL/Neon test branch:
PB10_TEST_DATABASE_URL=... pytest -q tests/test_database_pool_recovery_integration.py

This test terminates one backend session on the supplied test database; it must
never point at production.
"""
import os
import time

import psycopg
import pytest
from psycopg_pool import ConnectionPool


def test_pool_replaces_backend_terminated_on_disposable_test_branch():
    conninfo = os.getenv("PB10_TEST_DATABASE_URL")
    if not conninfo:
        pytest.skip("PB10_TEST_DATABASE_URL is not configured")

    host = conninfo.split("@", 1)[-1].split("/", 1)[0].lower()
    if "ep-ancient-cherry-arpqssmi" not in host and "pb10-test" not in host:
        pytest.skip("Set PB10_TEST_DATABASE_URL to the dedicated PB-10 disposable Neon branch")

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
