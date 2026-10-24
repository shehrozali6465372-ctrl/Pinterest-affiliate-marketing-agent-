"""PostgreSQL connection and persistence layer for Model 1."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

_pool: ConnectionPool | None = None
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_pool() -> ConnectionPool:
    """Create the pool lazily so liveness checks work without a DB connection."""
    global _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured; product persistence is unavailable.")
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=5,
            open=True,
        )
    return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    """Yield a pooled PostgreSQL connection."""
    with get_pool().connection() as conn:
        yield conn


def run_migrations() -> None:
    """Apply each numbered SQL migration once, in lexical order."""
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("SELECT pg_advisory_xact_lock(73219021)")
        for migration in sorted(_MIGRATIONS_DIR.glob("[0-9]*.sql")):
            version = migration.name
            existing = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (version,)
            ).fetchone()
            if existing:
                continue
            conn.execute(migration.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )


def get_product_by_idempotency_key(idempotency_key: str) -> dict | None:
    """Return a previously accepted product for a client retry key."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_name, product_details, image_url, affiliate_url, created_at
            FROM products WHERE idempotency_key = %s
            """,
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None


def create_product(
    *,
    product_name: str,
    product_details: str,
    image_url: str,
    affiliate_url: str,
    idempotency_key: str | None = None,
) -> dict:
    """Persist user-supplied product data and return the stored row."""
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO products (product_name, product_details, image_url, affiliate_url, idempotency_key)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, product_name, product_details, image_url, affiliate_url, created_at, idempotency_key
            """,
            (product_name, product_details, image_url, affiliate_url, idempotency_key),
        ).fetchone()
        return dict(row)


def get_product(product_id: int) -> dict | None:
    """Fetch a single persisted product."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_name, product_details, image_url, affiliate_url, created_at
            FROM products WHERE id = %s
            """,
            (product_id,),
        ).fetchone()
        return dict(row) if row else None


def create_content_version(
    *,
    product_id: int,
    provider: str,
    model_id: str,
    prompt_version: str,
    pin_idea: str,
    title: str,
    description: str,
    alt_text: str,
) -> dict:
    """Persist generated content as an auditable version for the supplied product."""
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (product_id,))
        version_number = conn.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM content_versions WHERE product_id = %s
            """,
            (product_id,),
        ).fetchone()["next_version"]
        row = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, product_id, version_number, provider, model_id, prompt_version,
                      pin_idea, title, description, alt_text, created_at
            """,
            (
                product_id, version_number, provider, model_id, prompt_version,
                pin_idea, title, description, alt_text,
            ),
        ).fetchone()
        return dict(row)


def get_content_version(product_id: int, content_version_id: int) -> dict | None:
    """Fetch one generated content version belonging to a product."""
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, product_id, version_number, provider, model_id, prompt_version,
                   pin_idea, title, description, alt_text, created_at
            FROM content_versions
            WHERE product_id = %s AND id = %s
            """,
            (product_id, content_version_id),
        ).fetchone()
        return dict(row) if row else None


def list_content_versions(product_id: int) -> list[dict]:
    """List saved content versions for a product in newest-first order."""
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, product_id, version_number, provider, model_id, prompt_version,
                   pin_idea, title, description, alt_text, created_at
            FROM content_versions
            WHERE product_id = %s
            ORDER BY version_number DESC
            """,
            (product_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def begin_publish_attempt(*, product_id: int, content_version_id: int, board_id: str) -> dict:
    """Reserve one publish attempt per version/board, preventing blind duplicates."""
    with connection() as conn:
        lock_key = f"{content_version_id}:{board_id}"
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (lock_key,))
        row = conn.execute(
            """
            SELECT * FROM pin_publications
            WHERE content_version_id = %s AND board_id = %s
            FOR UPDATE
            """,
            (content_version_id, board_id),
        ).fetchone()
        if row:
            state = row["status"]
            if state in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, **dict(row)}
            row = conn.execute(
                """
                UPDATE pin_publications
                SET status = 'pending', attempt_count = attempt_count + 1,
                    http_status = NULL, error_code = NULL, response_metadata = NULL,
                    last_attempt_at = now(), updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (row["id"],),
            ).fetchone()
            return {"blocked": False, **dict(row)}
        row = conn.execute(
            """
            INSERT INTO pin_publications
                (product_id, content_version_id, board_id, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING *
            """,
            (product_id, content_version_id, board_id),
        ).fetchone()
        return {"blocked": False, **dict(row)}


def finish_publish_attempt(
    publication_id: int,
    *,
    status: str,
    pinterest_pin_id: str | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    response_metadata: dict | None = None,
) -> dict:
    """Persist outcome metadata from the real Pinterest API, never an access token."""
    if status not in {"succeeded", "failed", "unknown"}:
        raise ValueError("unsupported publication status")
    if status == "succeeded" and not pinterest_pin_id:
        raise ValueError("successful publication requires a confirmed Pinterest Pin ID")
    with connection() as conn:
        row = conn.execute(
            """
            UPDATE pin_publications
            SET status = %s, pinterest_pin_id = %s, http_status = %s,
                error_code = %s, response_metadata = %s::jsonb, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (
                status, pinterest_pin_id, http_status, error_code,
                json.dumps(response_metadata or {}), publication_id,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("publish attempt was not found")
        return dict(row)


def close_pool() -> None:
    """Close the connection pool during application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
