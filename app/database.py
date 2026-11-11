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


def _model2_publication_assignment_block_reason(conn, account_id: str, niche_id: int) -> str | None:
    """Lock and validate the exact active Model 2 assignment before attribution."""
    assignment = conn.execute(
        """
        SELECT ap.status AS account_status,
               an.status AS assignment_status,
               n.status AS niche_status
        FROM model2_account_profiles AS ap
        JOIN model2_account_niches AS an
          ON an.account_id = ap.account_id
        JOIN model2_niches AS n
          ON n.id = an.niche_id
        WHERE ap.account_id = %s AND an.niche_id = %s
        FOR SHARE OF ap, an, n
        """,
        (account_id, niche_id),
    ).fetchone()
    if assignment is None or (
        assignment["account_status"] != "active"
        or assignment["assignment_status"] != "active"
        or assignment["niche_status"] != "active"
    ):
        return "niche_assignment_inactive"

    # Reuse the credential-vault's metadata-only check; never decrypt or refresh
    # a token inside the publication reservation transaction.
    from app.credential_vault import pinterest_account_is_connected_in_transaction

    if not pinterest_account_is_connected_in_transaction(conn, account_id):
        return "niche_account_not_connected"
    return None


def begin_publish_attempt(
    *,
    product_id: int,
    content_version_id: int,
    board_id: str,
    account_id: str | None = None,
    niche_id: int | None = None,
    attribution_source: str = "workflow",
) -> dict:
    """Reserve one publish attempt with account/niche locks before publication locks."""
    if niche_id is not None:
        if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
            raise ValueError("niche_id must be a positive integer")
        if not account_id or not account_id.strip():
            raise ValueError("account_id is required when niche_id is supplied")
        if attribution_source not in {"workflow", "operator_verified"}:
            raise ValueError("unsupported niche attribution source")

    with connection() as conn:
        # Read a non-locking hint first so terminal/idempotent outcomes can be
        # returned without acquiring account locks. This is rechecked under lock.
        hint = conn.execute(
            """
            SELECT pub.*, a.niche_id AS attributed_niche_id
            FROM pin_publications pub
            LEFT JOIN model2_publication_niche_attributions a
              ON a.publication_id = pub.id
            WHERE pub.content_version_id = %s AND pub.board_id = %s
            """,
            (content_version_id, board_id),
        ).fetchone()
        if hint:
            if hint.get("account_id") != account_id:
                return {"blocked": True, "account_mismatch": True, **dict(hint)}
            hinted_attribution = hint.get("attributed_niche_id")
            if niche_id is not None and hinted_attribution is not None and hinted_attribution != niche_id:
                return {"blocked": True, "niche_attribution_mismatch": True, **dict(hint)}
            if niche_id is not None and hinted_attribution is None and hint["status"] in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, "niche_attribution_missing": True, **dict(hint)}
            if hint["status"] in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, **dict(hint)}
            if hinted_attribution is not None and niche_id is None:
                # An attributed Model 2 retry must carry its exact niche context.
                # Do not acquire publication locks and then try to lock the
                # account/niche rows in the reverse order.
                return {"blocked": True, "niche_context_required": True, **dict(hint)}

        # Global lock order: account profile -> niche -> assignment -> credential
        # -> publication advisory lock -> publication row. Reconciliation follows
        # the same account-before-publication direction.
        if niche_id is not None:
            block_reason = _model2_publication_assignment_block_reason(conn, account_id, niche_id)
            if block_reason:
                return {"blocked": True, block_reason: True}

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
            attribution = None
            if niche_id is not None or state == "failed":
                attribution = conn.execute(
                    """
                    SELECT niche_id
                    FROM model2_publication_niche_attributions
                    WHERE publication_id = %s
                    """,
                    (row["id"],),
                ).fetchone()

            if niche_id is not None and attribution is not None:
                if attribution["niche_id"] != niche_id:
                    return {"blocked": True, "niche_attribution_mismatch": True, **dict(row)}
            if niche_id is not None and attribution is None and state in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, "niche_attribution_missing": True, **dict(row)}

            if state in {"succeeded", "pending", "unknown"}:
                return {"blocked": True, **dict(row)}

            if attribution is not None and niche_id is None:
                return {"blocked": True, "niche_context_required": True, **dict(row)}

            if attribution is None and niche_id is not None:
                conn.execute(
                    """
                    INSERT INTO model2_publication_niche_attributions
                        (publication_id, account_id, niche_id, attribution_source)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (row["id"], account_id, niche_id, attribution_source),
                )

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

        if niche_id is not None:
            conn.execute(
                """
                INSERT INTO model2_publication_niche_attributions
                    (publication_id, account_id, niche_id, attribution_source)
                VALUES (%s, %s, %s, %s)
                """,
                (row["id"], account_id, niche_id, attribution_source),
            )
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


def reconcile_unknown_publication_in_transaction(
    conn,
    publication_id: int,
    *,
    outcome: str,
    pinterest_pin_id: str | None = None,
    operator_evidence: str,
) -> dict:
    """Reconcile one publication using the caller's existing transaction.

    The caller owns transaction boundaries. This enables a scheduler job and its
    publication ledger row to be changed atomically without opening a second
    pooled connection. This helper never calls Pinterest or makes a publish call.
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

    conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"publication-reconcile:{publication_id}",),
    )
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


def reconcile_unknown_publication(
    publication_id: int, *, outcome: str, pinterest_pin_id: str | None = None,
    operator_evidence: str,
) -> dict:
    """Resolve an uncertain publish using its own transaction; never calls Pinterest."""
    # Validate caller input before acquiring a database connection. This keeps
    # malformed requests deterministic even when DATABASE_URL is unavailable.
    evidence = operator_evidence.strip()
    if not evidence or len(evidence) > 2000:
        raise ValueError("operator_evidence must be non-empty and at most 2000 characters")
    if outcome == "succeeded" and (not pinterest_pin_id or not pinterest_pin_id.strip()):
        raise ValueError("verified Pinterest Pin ID is required for succeeded reconciliation")
    if outcome == "failed" and pinterest_pin_id:
        raise ValueError("Pin ID must be omitted when confirming no Pin exists")
    if outcome not in {"succeeded", "failed"}:
        raise ValueError("outcome must be 'succeeded' or 'failed'")
    with connection() as conn:
        return reconcile_unknown_publication_in_transaction(
            conn,
            publication_id,
            outcome=outcome,
            pinterest_pin_id=pinterest_pin_id,
            operator_evidence=operator_evidence,
        )



def get_scheduler_job_reconciliation(job_id: int, *, account_id: str) -> dict | None:
    """Read-only, account-scoped reconciliation view; never contacts Pinterest."""
    with connection() as conn:
        job = conn.execute(
            """
            SELECT j.id AS job_id, j.status AS job_status, j.product_id,
                   j.pinterest_pin_id AS job_pin_id, j.idempotency_key,
                   s.id AS schedule_id, s.account_id, s.niche_id, s.status AS schedule_status
            FROM affiliate_pin_jobs j
            JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
            WHERE j.id = %s AND s.account_id = %s
            """,
            (job_id, account_id),
        ).fetchone()
        if not job:
            return None
        candidates = conn.execute(
            """
            SELECT pub.id AS publication_id, pub.status AS publication_status,
                   pub.account_id AS publication_account_id, pub.board_id,
                   pub.product_id, pub.content_version_id, pub.pinterest_pin_id,
                   a.niche_id AS attributed_niche_id
            FROM products p
            JOIN pin_publications pub ON pub.product_id = p.id
            JOIN content_versions cv
              ON cv.id = pub.content_version_id AND cv.product_id = p.id
            LEFT JOIN model2_publication_niche_attributions a
              ON a.publication_id = pub.id
            WHERE p.idempotency_key = %s
            ORDER BY pub.id
            """,
            (job["idempotency_key"],),
        ).fetchall()
        candidate = None
        linkage_status = "no_publication_candidate" if not candidates else "ambiguous_publication_candidates"
        if len(candidates) == 1:
            row = dict(candidates[0])
            if row["publication_account_id"] != account_id:
                linkage_status = "publication_account_mismatch"
            elif job["product_id"] is not None and job["product_id"] != row["product_id"]:
                linkage_status = "publication_product_mismatch"
            elif job["niche_id"] is not None and row["attributed_niche_id"] != job["niche_id"]:
                linkage_status = "publication_niche_attribution_missing_or_mismatched"
            elif job["niche_id"] is None and row["attributed_niche_id"] is not None:
                linkage_status = "legacy_model1_niche_attribution_mismatch"
            else:
                linkage_status = "matched"
                candidate = {
                    "publication_id": row["publication_id"],
                    "publication_status": row["publication_status"],
                    "board_id": row["board_id"],
                    "content_version_id": row["content_version_id"],
                    "pinterest_pin_id": row["pinterest_pin_id"],
                }
        return {
            "job_id": job["job_id"], "job_status": job["job_status"],
            "schedule_id": job["schedule_id"], "account_id": job["account_id"],
            "niche_id": job["niche_id"], "schedule_status": job["schedule_status"],
            "product_id": job["product_id"], "job_pin_id": job["job_pin_id"],
            "publication_candidate_count": len(candidates),
            "linkage_status": linkage_status,
            "publication": candidate,
            "read_only": True,
        }


def reconcile_scheduler_job(
    job_id: int, *, account_id: str, outcome: str,
    pinterest_pin_id: str | None, operator_evidence: str,
    confirm_pin_absent: bool = False,
) -> dict:
    """Atomically reconcile one uncertain scheduler job without provider calls."""
    evidence = operator_evidence.strip()
    if not account_id or not account_id.strip():
        raise ValueError("account_id is required")
    if not evidence or len(evidence) < 12 or len(evidence) > 2000:
        raise ValueError("operator_evidence must be between 12 and 2000 characters")
    if outcome not in {"succeeded", "failed"}:
        raise ValueError("outcome must be 'succeeded' or 'failed'")
    if outcome == "succeeded":
        if not pinterest_pin_id or not pinterest_pin_id.strip():
            raise ValueError("verified Pinterest Pin ID is required for succeeded reconciliation")
        if confirm_pin_absent:
            raise ValueError("confirm_pin_absent must be false for succeeded reconciliation")
        pin_id = pinterest_pin_id.strip()
    else:
        if pinterest_pin_id:
            raise ValueError("Pin ID must be omitted when confirming no Pin exists")
        if confirm_pin_absent is not True:
            raise ValueError("explicit confirm_pin_absent=true is required for failed reconciliation")
        pin_id = None

    with connection() as conn:
        # Read the immutable routing hint first, then follow the scheduler's
        # profile -> niche -> assignment -> schedule -> job lock order.
        hint = conn.execute(
            """
            SELECT s.id AS schedule_id, s.account_id, s.niche_id
            FROM affiliate_pin_jobs j
            JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
            WHERE j.id = %s
            """,
            (job_id,),
        ).fetchone()
        if not hint:
            raise LookupError("scheduler job was not found")
        if hint["account_id"] != account_id:
            raise PermissionError("scheduler job does not belong to the requested account")

        if hint["niche_id"] is not None:
            profile = conn.execute(
                "SELECT account_id FROM model2_account_profiles WHERE account_id = %s FOR UPDATE",
                (account_id,),
            ).fetchone()
            niche = conn.execute(
                "SELECT id FROM model2_niches WHERE id = %s FOR SHARE",
                (hint["niche_id"],),
            ).fetchone()
            assignment = conn.execute(
                """
                SELECT account_id, niche_id FROM model2_account_niches
                WHERE account_id = %s AND niche_id = %s FOR SHARE
                """,
                (account_id, hint["niche_id"]),
            ).fetchone()
            if not profile or not niche or not assignment:
                raise ValueError("Model 2 account/niche linkage is missing; job remains uncertain")

        schedule = conn.execute(
            """
            SELECT id, account_id, niche_id, status
            FROM affiliate_publishing_schedules
            WHERE id = %s FOR UPDATE
            """,
            (hint["schedule_id"],),
        ).fetchone()
        if not schedule or schedule["account_id"] != account_id or schedule["niche_id"] != hint["niche_id"]:
            raise ValueError("schedule linkage changed; job remains uncertain")

        job = conn.execute(
            """
            SELECT id, schedule_id, status, idempotency_key, product_id, pinterest_pin_id
            FROM affiliate_pin_jobs WHERE id = %s FOR UPDATE
            """,
            (job_id,),
        ).fetchone()
        if not job:
            raise LookupError("scheduler job was not found")
        if job["status"] != "uncertain":
            raise ValueError("only uncertain scheduler jobs may be reconciled")

        candidates = conn.execute(
            """
            SELECT pub.id AS publication_id, pub.product_id, pub.content_version_id,
                   pub.board_id, pub.account_id, pub.status AS publication_status,
                   pub.pinterest_pin_id, a.niche_id AS attributed_niche_id
            FROM products p
            JOIN pin_publications pub ON pub.product_id = p.id
            JOIN content_versions cv
              ON cv.id = pub.content_version_id AND cv.product_id = p.id
            LEFT JOIN model2_publication_niche_attributions a
              ON a.publication_id = pub.id
            WHERE p.idempotency_key = %s
            ORDER BY pub.id
            """,
            (job["idempotency_key"],),
        ).fetchall()
        if len(candidates) > 1:
            raise ValueError("multiple publication candidates exist; manual investigation is required")
        publication = dict(candidates[0]) if candidates else None
        if publication:
            if publication["account_id"] != account_id:
                raise ValueError("publication account does not match scheduler account")
            if job["product_id"] is not None and job["product_id"] != publication["product_id"]:
                raise ValueError("publication product does not match scheduler job")
            if schedule["niche_id"] is not None:
                if publication["attributed_niche_id"] != schedule["niche_id"]:
                    raise ValueError("publication niche attribution is missing or mismatched")
            elif publication["attributed_niche_id"] is not None:
                raise ValueError("legacy scheduler job cannot reconcile a Model 2-attributed publication")

            publication = conn.execute(
                "SELECT * FROM pin_publications WHERE id = %s FOR UPDATE",
                (publication["publication_id"],),
            ).fetchone()
            if publication is None:
                raise ValueError("publication candidate disappeared; job remains uncertain")
            if publication["account_id"] != account_id:
                raise ValueError("publication account linkage is ambiguous")

            if publication["status"] == "succeeded":
                if outcome != "succeeded" or publication["pinterest_pin_id"] != pin_id:
                    raise ValueError("publication ledger already confirms a different successful outcome")
            elif publication["status"] in {"pending", "unknown"}:
                if publication["status"] == "pending":
                    stale = conn.execute(
                        "SELECT updated_at <= now() - interval '10 minutes' AS stale FROM pin_publications WHERE id = %s",
                        (publication["id"],),
                    ).fetchone()
                    if not stale or not stale["stale"]:
                        raise ValueError("pending publication must be at least 10 minutes old before reconciliation")
            elif publication["status"] == "failed":
                if outcome != "failed":
                    raise ValueError("failed publication cannot be promoted to succeeded")
            else:
                raise ValueError("unsupported publication ledger state")

        if outcome == "succeeded" and publication is None:
            raise ValueError("no publication ledger row exists; success cannot be proven")

        audit = conn.execute(
            """
            INSERT INTO affiliate_job_reconciliation_audit
                (job_id, schedule_id, account_id, publication_id, outcome,
                 pinterest_pin_id, operator_evidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, reconciled_at
            """,
            (job_id, schedule["id"], account_id,
             publication["id"] if publication else None, outcome, pin_id, evidence),
        ).fetchone()

        if publication and publication["status"] != "succeeded":
            next_error = None if outcome == "succeeded" else "operator_verified_pin_absent"
            updated_publication = conn.execute(
                """
                UPDATE pin_publications
                SET status = %s, pinterest_pin_id = %s, error_code = %s,
                    response_metadata = COALESCE(response_metadata, '{}'::jsonb)
                        || jsonb_build_object('scheduler_reconciliation', jsonb_build_object(
                            'audit_id', %s::bigint, 'outcome', %s::text)),
                    updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (outcome, pin_id, next_error, audit["id"], outcome, publication["id"]),
            ).fetchone()
            if not updated_publication:
                raise RuntimeError("publication ledger update failed")

        updated_job = conn.execute(
            """
            UPDATE affiliate_pin_jobs
            SET status = %s, pinterest_pin_id = %s,
                product_id = COALESCE(product_id, %s),
                finished_at = now(), locked_at = NULL,
                safe_error_code = %s
            WHERE id = %s AND status = 'uncertain'
            RETURNING id, status, product_id, pinterest_pin_id
            """,
            (outcome, pin_id,
             publication["product_id"] if publication else job["product_id"],
             None if outcome == "succeeded" else "operator_verified_pin_absent",
             job_id),
        ).fetchone()
        if not updated_job:
            raise ValueError("scheduler job state changed during reconciliation")

        conn.execute(
            """
            UPDATE affiliate_publishing_schedules s
            SET status = 'completed', updated_at = now()
            WHERE s.id = %s AND s.status = 'active'
              AND NOT EXISTS (
                SELECT 1 FROM affiliate_pin_jobs j
                WHERE j.schedule_id = s.id
                  AND j.status IN ('queued', 'processing', 'uncertain')
              )
            """,
            (schedule["id"],),
        )
        return {
            "job_id": updated_job["id"], "status": updated_job["status"],
            "product_id": updated_job["product_id"],
            "pinterest_pin_id": updated_job["pinterest_pin_id"],
            "publication_id": publication["id"] if publication else None,
            "audit_id": audit["id"], "account_id": account_id,
            "reconciled": True, "read_only": False,
        }


def close_pool() -> None:
    """Close the connection pool during application shutdown."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def claim_pinterest_board_operation(
    *, account_id: str, idempotency_key: str, request_fingerprint: str,
) -> dict:
    """Claim a board-create key or return its durable terminal/in-flight state.

    An in-progress row is deliberately never lease-stolen: after process death
    the provider may already have created the board, so retrying is unsafe.
    """
    with connection() as conn:
        inserted = conn.execute(
            """INSERT INTO pinterest_board_operations
                   (account_id, idempotency_key, request_fingerprint, status)
               VALUES (%s, %s, %s, 'in_progress')
               ON CONFLICT (account_id, idempotency_key) DO NOTHING
               RETURNING status, result""",
            (account_id, idempotency_key, request_fingerprint),
        ).fetchone()
        if inserted:
            return {"status": "acquired"}
        row = conn.execute(
            """SELECT request_fingerprint, status, result
               FROM pinterest_board_operations
               WHERE account_id = %s AND idempotency_key = %s
               FOR UPDATE""",
            (account_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest board operation idempotency row disappeared")
        if row["request_fingerprint"] != request_fingerprint:
            raise ValueError("idempotency_key_payload_mismatch")
        result = row.get("result")
        if isinstance(result, str):
            result = json.loads(result)
        return {"status": row["status"], "result": result}


def complete_pinterest_board_operation(
    *, account_id: str, idempotency_key: str, result: dict,
) -> None:
    """Persist the provider response before returning success to the caller."""
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_board_operations
               SET status = 'succeeded', result = %s::jsonb, updated_at = now()
               WHERE account_id = %s AND idempotency_key = %s AND status = 'in_progress'
               RETURNING id""",
            (json.dumps(result), account_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest board operation could not be finalized")


def mark_pinterest_board_operation_uncertain(
    *, account_id: str, idempotency_key: str,
) -> None:
    """Persist an ambiguous provider outcome; the operation must not be replayed."""
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_board_operations
               SET status = 'uncertain', updated_at = now()
               WHERE account_id = %s AND idempotency_key = %s AND status = 'in_progress'
               RETURNING id""",
            (account_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest board operation uncertainty could not be persisted")


def mark_pinterest_board_operation_failed(
    *, account_id: str, idempotency_key: str,
) -> None:
    """Persist a definitive provider rejection without allowing key reuse."""
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_board_operations
               SET status = 'failed', updated_at = now()
               WHERE account_id = %s AND idempotency_key = %s AND status = 'in_progress'
               RETURNING id""",
            (account_id, idempotency_key),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest board operation failure could not be persisted")


def claim_pinterest_refresh_operation(*, account_id: str, request_fingerprint: str) -> dict:
    """Claim one refresh attempt for a specific encrypted-token generation.

    A token-generation fingerprint is derived from the current access and
    refresh token values; raw token material is never persisted in this ledger.
    An ambiguous attempt remains blocked for that exact token generation.
    """
    with connection() as conn:
        inserted = conn.execute(
            """INSERT INTO pinterest_refresh_operations
                   (account_id, request_fingerprint, status)
               VALUES (%s, %s, 'in_progress')
               ON CONFLICT (account_id, request_fingerprint) DO NOTHING
               RETURNING status""",
            (account_id, request_fingerprint),
        ).fetchone()
        if inserted:
            return {"status": "acquired"}
        row = conn.execute(
            """SELECT status FROM pinterest_refresh_operations
               WHERE account_id = %s AND request_fingerprint = %s FOR UPDATE""",
            (account_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest refresh operation idempotency row disappeared")
        return {"status": row["status"]}


def complete_pinterest_refresh_operation(*, account_id: str, request_fingerprint: str) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_refresh_operations
               SET status = 'succeeded', updated_at = now()
               WHERE account_id = %s AND request_fingerprint = %s AND status = 'in_progress'
               RETURNING id""",
            (account_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest refresh operation could not be finalized")


def mark_pinterest_refresh_operation_uncertain(*, account_id: str, request_fingerprint: str) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_refresh_operations
               SET status = 'uncertain', updated_at = now()
               WHERE account_id = %s AND request_fingerprint = %s AND status = 'in_progress'
               RETURNING id""",
            (account_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest refresh operation uncertainty could not be persisted")


def mark_pinterest_refresh_operation_failed(*, account_id: str, request_fingerprint: str) -> None:
    with connection() as conn:
        row = conn.execute(
            """UPDATE pinterest_refresh_operations
               SET status = 'failed', updated_at = now()
               WHERE account_id = %s AND request_fingerprint = %s AND status = 'in_progress'
               RETURNING id""",
            (account_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise RuntimeError("Pinterest refresh operation failure could not be persisted")
