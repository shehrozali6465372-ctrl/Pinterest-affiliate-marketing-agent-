"""Small PostgreSQL persistence layer for product intake.

Connection is optional during local startup. Persistence methods fail explicitly if
DATABASE_URL is absent; the API must not claim data was saved when it was not.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.main import settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Create the pool lazily so health checks work without a database configured."""
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
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def initialize_schema() -> None:
    """Apply the initial idempotent schema. Production migrations will version changes."""
    with connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id BIGSERIAL PRIMARY KEY,
                product_name TEXT NOT NULL CHECK (char_length(product_name) BETWEEN 1 AND 300),
                product_details TEXT NOT NULL CHECK (char_length(product_details) BETWEEN 1 AND 10000),
                image_url TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
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


def close_pool() -> None:
    """Close the connection pool, primarily useful for clean shutdowns and tests."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
