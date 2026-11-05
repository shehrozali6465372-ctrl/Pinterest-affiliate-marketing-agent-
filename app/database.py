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

class DatabaseConfigurationError(RuntimeError):
    """Raised when the database connection cannot be configured."""


_pool: ConnectionPool | None = None
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def get_pool() -> ConnectionPool:
    """Create the pool lazily so liveness checks work without a DB connection."""
    global _pool
    if not settings.database_url:
        raise DatabaseConfigurationError("DATABASE_URL is not configured; product persistence is unavailable.")
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            kwargs={"row_factory": dict_row},
            min_size=1,
            max_size=5,
            # Validate idle connections on checkout so Neon/server-side idle
            # disconnects are discarded and replaced instead of handed to a query.
            check=ConnectionPool.check_connection,
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



def create_product_with_content_version(
    *,
    product_name: str,
    product_details: str,
    image_url: str | None,
    affiliate_url: str,
    idempotency_key: str,
    request_fingerprint: str,
    lease_token: str | None = None,
    provider: str,
    model_id: str,
    prompt_version: str,
    pin_idea: str,
    title: str,
    description: str,
    alt_text: str,
) -> tuple[dict, dict]:
    """Atomically persist a product and its first content version.

    Both inserts share one pooled connection/transaction so a failed content
    insert cannot leave an idempotency key attached to a half-created product.
    """
    with connection() as conn:
        def finalize_generation(product_id: int) -> None:
            if lease_token is None:
                return
            finalized = conn.execute(
                """UPDATE workflow_generation_reservations
                   SET status = 'persisted', product_id = %s, image_data_url = NULL, image_model = NULL,
                       generated_content = NULL, content_model = NULL, lease_token = NULL,
                       lease_expires_at = NULL, updated_at = now()
                   WHERE idempotency_key = %s AND lease_token = %s::uuid AND status = 'generating'
                     AND lease_expires_at > clock_timestamp()
                   RETURNING idempotency_key""",
                (product_id, idempotency_key, lease_token),
            ).fetchone()
            if finalized is None:
                raise RuntimeError("workflow generation lease lost before atomic product/content completion")

        product = conn.execute(
            """
            INSERT INTO products
                (product_name, product_details, image_url, affiliate_url,
                 idempotency_key, request_fingerprint)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
            DO NOTHING
            RETURNING id, product_name, product_details, image_url, affiliate_url,
                      created_at, idempotency_key, request_fingerprint
            """,
            (product_name, product_details, image_url, affiliate_url,
             idempotency_key, request_fingerprint),
        ).fetchone()
        if product is None:
            # The unique index serializes concurrent requests sharing this key.
            # Re-read the winner after ON CONFLICT waits for its transaction.
            product = conn.execute(
                """SELECT id, product_name, product_details, image_url, affiliate_url,
                          created_at, idempotency_key, request_fingerprint
                   FROM products WHERE idempotency_key = %s FOR UPDATE""",
                (idempotency_key,),
            ).fetchone()
            if product is None:
                raise RuntimeError("workflow idempotency record disappeared during conflict recovery")
            if product.get("request_fingerprint") != request_fingerprint:
                raise ValueError("idempotency_key_payload_mismatch")
            content = conn.execute(
                """SELECT id, product_id, version_number, provider, model_id, prompt_version,
                          pin_idea, title, description, alt_text, created_at
                   FROM content_versions WHERE product_id = %s AND version_number = 1""",
                (product["id"],),
            ).fetchone()
            if content is None:
                raise RuntimeError("workflow idempotency record has no initial content version")
            finalize_generation(product["id"])
            return dict(product), dict(content)

        content = conn.execute(
            """
            INSERT INTO content_versions
                (product_id, version_number, provider, model_id, prompt_version,
                 pin_idea, title, description, alt_text)
            VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, product_id, version_number, provider, model_id, prompt_version,
                      pin_idea, title, description, alt_text, created_at
            """,
            (
                product["id"], provider, model_id, prompt_version,
                pin_idea, title, description, alt_text,
            ),
        ).fetchone()
        finalize_generation(product["id"])
        return dict(product), dict(content)



def persist_manual_publish_draft(
    *, title: str, description: str, image_url: str, affiliate_url: str,
    idempotency_key: str, request_fingerprint: str,
) -> tuple[dict, dict, bool]:
    """Atomically create or recover an identical manual draft by idempotency key."""
    with connection() as conn:
        product = conn.execute(
            """INSERT INTO products
                   (product_name, product_details, image_url, affiliate_url,
                    idempotency_key, request_fingerprint)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL
               DO NOTHING
               RETURNING id, product_name, product_details, image_url, affiliate_url,
                         created_at, idempotency_key, request_fingerprint""",
            (title, description or title, image_url, affiliate_url, idempotency_key, request_fingerprint),
        ).fetchone()
        created = product is not None
        if created:
            content = conn.execute(
                """INSERT INTO content_versions
                       (product_id, version_number, provider, model_id, prompt_version,
                        pin_idea, title, description, alt_text)
                   VALUES (%s, 1, 'manual', 'hub-manual', 'manual-v1', %s, %s, %s, %s)
                   RETURNING id, product_id, version_number, provider, model_id,
                             prompt_version, pin_idea, title, description, alt_text, created_at""",
                (product['id'], description or title, title, description or '', ''),
            ).fetchone()
            return dict(product), dict(content), True

        product = conn.execute(
            """SELECT id, product_name, product_details, image_url, affiliate_url,
                      created_at, idempotency_key, request_fingerprint
               FROM products WHERE idempotency_key = %s FOR UPDATE""",
            (idempotency_key,),
        ).fetchone()
        if product is None:
            raise RuntimeError("idempotency record disappeared during recovery")
        if product.get('request_fingerprint') != request_fingerprint:
            raise ValueError("idempotency_key_payload_mismatch")
        content = conn.execute(
            """SELECT id, product_id, version_number, provider, model_id, prompt_version,
                      pin_idea, title, description, alt_text, created_at
               FROM content_versions WHERE product_id = %s AND version_number = 1""",
            (product['id'],),
        ).fetchone()
        if content is None:
            raise RuntimeError("manual draft exists without its content version")
        return dict(product), dict(content), False


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



def reserve_workflow_generation(
    *, idempotency_key: str, request_fingerprint: str, lease_token: str, lease_seconds: int = 600,
) -> dict:
    """Atomically acquire or recover a workflow-generation lease.

    A live lease prevents concurrent provider calls. Cached image/content survive
    retryable provider failures so retries do not pay for completed stages again.
    """
    with connection() as conn:
        row = conn.execute(
            """INSERT INTO workflow_generation_reservations
                   (idempotency_key, request_fingerprint, status, lease_token, lease_expires_at)
               VALUES (%s, %s, 'generating', %s::uuid, clock_timestamp() + (%s * interval '1 second'))
               ON CONFLICT (idempotency_key) DO NOTHING
               RETURNING *""",
            (idempotency_key, request_fingerprint, lease_token, lease_seconds),
        ).fetchone()
        if row:
            return {**dict(row), "acquired": True}
        row = conn.execute(
            "SELECT * FROM workflow_generation_reservations WHERE idempotency_key = %s FOR UPDATE",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError("workflow generation reservation disappeared")
        if row["request_fingerprint"] != request_fingerprint:
            raise ValueError("idempotency_key_payload_mismatch")
        if row["status"] == "persisted":
            return {**dict(row), "acquired": False}
        if row["status"] == "generating" and row["lease_expires_at"] > conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]:
            return {**dict(row), "acquired": False}
        row = conn.execute(
            """UPDATE workflow_generation_reservations
               SET status = 'generating', lease_token = %s::uuid,
                   lease_expires_at = clock_timestamp() + (%s * interval '1 second'), updated_at = now()
               WHERE idempotency_key = %s RETURNING *""",
            (lease_token, lease_seconds, idempotency_key),
        ).fetchone()
        return {**dict(row), "acquired": True}


def save_workflow_generation_image(
    *, idempotency_key: str, lease_token: str, image_data_url: str, image_model: str,
) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE workflow_generation_reservations
               SET image_data_url = %s, image_model = %s, updated_at = now()
               WHERE idempotency_key = %s AND lease_token = %s::uuid AND status = 'generating'
                     AND lease_expires_at > clock_timestamp()
               RETURNING idempotency_key""",
            (image_data_url, image_model, idempotency_key, lease_token),
        ).fetchone()
        if row is None:
            raise RuntimeError("workflow generation lease lost before image checkpoint")


def save_workflow_generation_content(
    *, idempotency_key: str, lease_token: str, generated_content: dict, content_model: str,
) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE workflow_generation_reservations
               SET generated_content = %s::jsonb, content_model = %s, updated_at = now()
               WHERE idempotency_key = %s AND lease_token = %s::uuid AND status = 'generating'
                     AND lease_expires_at > clock_timestamp()
               RETURNING idempotency_key""",
            (json.dumps(generated_content), content_model, idempotency_key, lease_token),
        ).fetchone()
        if row is None:
            raise RuntimeError("workflow generation lease lost before content checkpoint")


def release_workflow_generation(*, idempotency_key: str, lease_token: str) -> None:
    """Make a failed generation retryable while preserving completed provider stages."""
    with connection() as conn:
        conn.execute(
            """UPDATE workflow_generation_reservations
               SET status = 'retryable', lease_token = NULL, lease_expires_at = NULL, updated_at = now()
               WHERE idempotency_key = %s AND lease_token = %s::uuid AND status = 'generating'""",
            (idempotency_key, lease_token),
        )


def complete_workflow_generation(*, idempotency_key: str, lease_token: str, product_id: int) -> None:
    """Mark provider work consumed by a durable product/content transaction and clear bulky cache."""
    with connection() as conn:
        row = conn.execute(
            """UPDATE workflow_generation_reservations
               SET status = 'persisted', product_id = %s, image_data_url = NULL, image_model = NULL,
                   generated_content = NULL, content_model = NULL, lease_token = NULL,
                   lease_expires_at = NULL, updated_at = now()
               WHERE idempotency_key = %s AND lease_token = %s::uuid AND status = 'generating'
                     AND lease_expires_at > clock_timestamp()
               RETURNING idempotency_key""",
            (product_id, idempotency_key, lease_token),
        ).fetchone()
        if row is None:
            raise RuntimeError("workflow generation lease lost before completion")

def cleanup_expired_workflow_checkpoints(*, retention_hours: int = 72, batch_size: int = 500) -> int:
    """Clear old retry checkpoint payloads while preserving idempotency tombstones.

    Images are generated as data URLs and are not uploaded to a separate image host.
    This only clears temporary database checkpoint fields; reservation rows and
    request fingerprints remain so an old Idempotency-Key cannot be reused.
    """
    if not 1 <= retention_hours <= 720:
        raise ValueError("retention_hours must be between 1 and 720")
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size must be between 1 and 5000")
    with connection() as conn:
        rows = conn.execute(
            """WITH expired AS (
                   SELECT idempotency_key
                   FROM workflow_generation_reservations
                   WHERE status IN ('retryable', 'generating')
                     AND (status <> 'generating' OR lease_expires_at <= clock_timestamp())
                     AND updated_at < clock_timestamp() - (%s * interval '1 hour')
                     AND (image_data_url IS NOT NULL OR generated_content IS NOT NULL)
                   ORDER BY updated_at
                   FOR UPDATE SKIP LOCKED
                   LIMIT %s
               )
               UPDATE workflow_generation_reservations AS reservation
               SET image_data_url = NULL, image_model = NULL,
                   generated_content = NULL, content_model = NULL,
                   updated_at = clock_timestamp()
               FROM expired
               WHERE reservation.idempotency_key = expired.idempotency_key
               RETURNING reservation.idempotency_key""",
            (retention_hours, batch_size),
        ).fetchall()
        return len(rows)


def begin_publish_attempt(
    *, product_id: int, content_version_id: int, board_id: str, account_id: str | None = None
) -> dict:
    """Reserve one publish attempt per version/board, and retain its owning account."""
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
            if row.get("account_id") != account_id:
                return {"blocked": True, "account_mismatch": True, **dict(row)}
            state = row["status"]
            if state in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, **dict(row)}
            row = conn.execute(
                """
                UPDATE pin_publications
                SET status = 'pending', attempt_count = attempt_count + 1,
                    account_id = COALESCE(account_id, %s),
                    http_status = NULL, error_code = NULL, response_metadata = NULL,
                    last_attempt_at = now(), updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (account_id, row["id"]),
            ).fetchone()
            return {"blocked": False, **dict(row)}
        row = conn.execute(
            """
            INSERT INTO pin_publications
                (product_id, content_version_id, board_id, account_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING *
            """,
            (product_id, content_version_id, board_id, account_id),
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



def get_publication(publication_id: int) -> dict | None:
    """Return only the stored publication fields needed for operator reconciliation."""
    with connection() as conn:
        row = conn.execute(
            """SELECT id, product_id, content_version_id, board_id, account_id,
                      status, attempt_count, pinterest_pin_id, http_status,
                      error_code, response_metadata, created_at, updated_at
               FROM pin_publications WHERE id = %s""",
            (publication_id,),
        ).fetchone()
        return dict(row) if row else None


def reconcile_unknown_publication(
    publication_id: int, *, outcome: str, pinterest_pin_id: str | None = None,
    operator_evidence: str,
) -> dict:
    """Resolve an uncertain publish only after an operator verifies Pinterest state.

    `outcome='succeeded'` requires a Pin ID copied from the verified board listing.
    `outcome='failed'` requires explicit operator confirmation that the Pin is absent.
    This function never calls Pinterest and never makes an uncertain result retryable
    without the caller supplying that verification evidence.
    """
    evidence = operator_evidence.strip()
    if not evidence or len(evidence) > 2000:
        raise ValueError("operator_evidence must be non-empty and at most 2000 characters")
    if outcome == "succeeded":
        if not pinterest_pin_id or not pinterest_pin_id.strip():
            raise ValueError("verified Pinterest Pin ID is required for succeeded reconciliation")
        next_status = "succeeded"
        pin_id = pinterest_pin_id.strip()
    elif outcome == "failed":
        if pinterest_pin_id:
            raise ValueError("Pin ID must be omitted when confirming no Pin exists")
        next_status = "failed"
        pin_id = None
    else:
        raise ValueError("outcome must be 'succeeded' or 'failed'")

    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"publication-reconcile:{publication_id}",))
        row = conn.execute(
            "SELECT * FROM pin_publications WHERE id = %s FOR UPDATE",
            (publication_id,),
        ).fetchone()
        if row is None:
            raise LookupError("publication record was not found")
        if row["status"] == "pending":
            stale = conn.execute(
                """SELECT updated_at <= now() - interval '10 minutes' AS stale
                   FROM pin_publications WHERE id = %s""",
                (publication_id,),
            ).fetchone()
            if not stale or not stale["stale"]:
                raise ValueError("pending publication must be at least 10 minutes old before operator reconciliation")
        elif row["status"] != "unknown":
            raise ValueError("only unknown or stale pending publications may be reconciled")
        if next_status == "succeeded":
            saved = conn.execute(
                """UPDATE pin_publications
                   SET status = 'succeeded', pinterest_pin_id = %s,
                       error_code = NULL,
                       response_metadata = COALESCE(response_metadata, '{}'::jsonb)
                           || jsonb_build_object('reconciliation', jsonb_build_object(
                               'method', 'operator_board_verification', 'evidence', %s::text)),
                       updated_at = now()
                   WHERE id = %s RETURNING *""",
                (pin_id, evidence, publication_id),
            ).fetchone()
        else:
            saved = conn.execute(
                """UPDATE pin_publications
                   SET status = 'failed', pinterest_pin_id = NULL,
                       error_code = 'operator_verified_pin_absent',
                       response_metadata = COALESCE(response_metadata, '{}'::jsonb)
                           || jsonb_build_object('reconciliation', jsonb_build_object(
                               'method', 'operator_board_verification', 'evidence', %s::text)),
                       updated_at = now()
                   WHERE id = %s RETURNING *""",
                (evidence, publication_id),
            ).fetchone()
        if saved is None:
            raise RuntimeError("publication reconciliation did not persist")
        return dict(saved)


def close_pool() -> None:
    """Close the connection pool during application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
