"""PostgreSQL connection and persistence layer for Model 1."""
from __future__ import annotations

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


def create_product(
    *,
    product_name: str,
    product_details: str,
    image_url: str,
    affiliate_url: str,
) -> dict:
    """Persist user-supplied product data and return the stored row."""
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO products (product_name, product_details, image_url, affiliate_url)
            VALUES (%s, %s, %s, %s)
            RETURNING id, product_name, product_details, image_url, affiliate_url, created_at
            """,
            (product_name, product_details, image_url, affiliate_url),
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


def close_pool() -> None:
    """Close the connection pool during application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
