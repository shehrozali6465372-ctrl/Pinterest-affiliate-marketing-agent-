[Reading 79 lines from start (total: 79 lines, 0 remaining)]

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

    # Require explicit opt-in and reject known production-ish targets.
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

        # Terminate only the disposable pool backend. PostgreSQL may also close
        # the admin session executing pg_terminate_backend; that disconnect is
        # expected and handled, while the pool's backend is the target.
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
            except Exception as exc:  # retry transient reconnect interval only
                last_error = type(exc).__name__
                time.sleep(0.25)

        assert replacement_pid is not None, f"Pool did not recover; last exception={last_error}"
        assert replacement_pid != stale_pid
    finally:
        pool.close()

[executed on device: localhost (bb54f029-ff20-4907-ad1f-8b963b1958c1)]

### PB-10 integration CI fix and current state — 2026-10-30

- PR #34 initial CI failed at test collection because the GitHub file contained a tool transcript footer after the last line. The local source file was clean; this was a GitHub file-content ingestion issue, not a test logic failure. The source has been corrected and its tail re-read to confirm only Python code remains.
- Local disposable-branch test already passed: backend PID was terminated on the dedicated Neon child branch, then pooled query recovered using a different PID; `SELECT 1` passed. Local focused suite: 7 passed.
- PR #34 still requires a fresh exact-head CI result and Codex review. Do not merge or deploy while those are pending.
