"""Transactional Model 2 account and niche repositories.

All SQL is parameterized and scoped by canonical account_id. This module does
not call Pinterest, OAuth, the publishing gateway, or the analytics pipeline.
"""
from __future__ import annotations

from typing import TypeVar

from psycopg.errors import UniqueViolation

from app.credential_vault import pinterest_account_is_connected_in_transaction
from app.database import connection
from app.model2_domain import (
    AccountNicheAssignmentInput,
    AccountProfileInput,
    NicheInput,
)

T = TypeVar("T")


class Model2RepositoryError(RuntimeError):
    """Base class for safe Model 2 repository failures."""


class Model2NotFoundError(Model2RepositoryError):
    """The requested Model 2 account, niche, or mapping does not exist."""


class Model2ConflictError(Model2RepositoryError):
    """A requested state conflicts with current Model 2 registry state."""


class Model2AccountNotConnectedError(Model2ConflictError):
    """The Pinterest credential row is absent or not in connected state."""


def _validated(model_type: type[T], payload: T) -> T:
    """Revalidate mutable Pydantic instances at the persistence boundary."""
    if not hasattr(payload, "model_dump"):
        raise TypeError("payload must be a validated Model 2 domain model")
    return model_type.model_validate(payload.model_dump())


def _row(row):
    return dict(row) if row is not None else None


def save_account_profile(payload: AccountProfileInput) -> dict:
    """Create/update profile metadata; active profiles require a connected account."""
    profile = _validated(AccountProfileInput, payload)
    with connection() as conn:
        existing = conn.execute(
            """
            SELECT account_id
            FROM model2_account_profiles
            WHERE account_id = %s
            FOR UPDATE
            """,
            (profile.account_id,),
        ).fetchone()

        # A new profile is explicit onboarding and always requires a connected
        # credential. Reactivation also requires a currently connected account.
        if existing is None or profile.status == "active":
            if not pinterest_account_is_connected_in_transaction(conn, profile.account_id):
                raise Model2AccountNotConnectedError(
                    "Pinterest account must be connected before profile creation or activation"
                )

        row = conn.execute(
            """
            INSERT INTO model2_account_profiles
                (account_id, display_name, status, timezone)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (account_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                status = EXCLUDED.status,
                timezone = EXCLUDED.timezone,
                updated_at = now()
            RETURNING account_id, display_name, status, timezone, created_at, updated_at
            """,
            (profile.account_id, profile.display_name, profile.status, profile.timezone),
        ).fetchone()

        if profile.status == "paused":
            # Pause mappings but retain rows and primary flags for audit/history.
            conn.execute(
                """
                UPDATE model2_account_niches
                SET status = 'paused', updated_at = now()
                WHERE account_id = %s AND status = 'active'
                """,
                (profile.account_id,),
            )
        return dict(row)


def get_account_profile(account_id: str) -> dict | None:
    account_id = AccountProfileInput(account_id=account_id).account_id
    with connection() as conn:
        row = conn.execute(
            """
            SELECT account_id, display_name, status, timezone, created_at, updated_at
            FROM model2_account_profiles
            WHERE account_id = %s
            """,
            (account_id,),
        ).fetchone()
    return _row(row)


def list_account_profiles() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT account_id, display_name, status, timezone, created_at, updated_at
            FROM model2_account_profiles
            ORDER BY created_at, account_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def create_niche(payload: NicheInput) -> dict:
    niche = _validated(NicheInput, payload)
    with connection() as conn:
        row = conn.execute(
            """
            INSERT INTO model2_niches
                (slug, display_name, description, default_region, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
            RETURNING id, slug, display_name, description, default_region, status,
                      created_at, updated_at
            """,
            (niche.slug, niche.display_name, niche.description, niche.default_region, niche.status),
        ).fetchone()
        if row is None:
            raise Model2ConflictError("A niche with this slug already exists")
        return dict(row)


def update_niche(niche_id: int, payload: NicheInput) -> dict:
    if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
        raise ValueError("niche_id must be a positive integer")
    niche = _validated(NicheInput, payload)
    with connection() as conn:
        try:
            row = conn.execute(
                """
                UPDATE model2_niches
                SET slug = %s, display_name = %s, description = %s,
                    default_region = %s, status = %s, updated_at = now()
                WHERE id = %s
                RETURNING id, slug, display_name, description, default_region, status,
                          created_at, updated_at
                """,
                (niche.slug, niche.display_name, niche.description, niche.default_region,
                 niche.status, niche_id),
            ).fetchone()
        except UniqueViolation as exc:
            raise Model2ConflictError("A niche with this slug already exists") from exc
        if row is None:
            raise Model2NotFoundError("Niche does not exist")
        if niche.status == "archived":
            # Archival preserves mappings and attribution but pauses active use.
            conn.execute(
                """
                UPDATE model2_account_niches
                SET status = 'paused', updated_at = now()
                WHERE niche_id = %s AND status = 'active'
                """,
                (niche_id,),
            )
        return dict(row)


def get_niche(niche_id: int) -> dict | None:
    if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
        raise ValueError("niche_id must be a positive integer")
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, slug, display_name, description, default_region, status,
                   created_at, updated_at
            FROM model2_niches
            WHERE id = %s
            """,
            (niche_id,),
        ).fetchone()
    return _row(row)


def list_niches(*, include_archived: bool = True) -> list[dict]:
    if not isinstance(include_archived, bool):
        raise ValueError("include_archived must be a boolean")
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, slug, display_name, description, default_region, status,
                   created_at, updated_at
            FROM model2_niches
            WHERE (%s OR status = 'active')
            ORDER BY slug, id
            """,
            (include_archived,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_account_niche_assignment(payload: AccountNicheAssignmentInput) -> dict:
    """Atomically save one mapping and serialize primary selection per account."""
    assignment = _validated(AccountNicheAssignmentInput, payload)
    with connection() as conn:
        profile = conn.execute(
            """
            SELECT status
            FROM model2_account_profiles
            WHERE account_id = %s
            FOR UPDATE
            """,
            (assignment.account_id,),
        ).fetchone()
        if profile is None:
            raise Model2NotFoundError("Account profile does not exist")

        niche = conn.execute(
            """
            SELECT status
            FROM model2_niches
            WHERE id = %s
            FOR SHARE
            """,
            (assignment.niche_id,),
        ).fetchone()
        if niche is None:
            raise Model2NotFoundError("Niche does not exist")

        if assignment.status == "active":
            if profile["status"] != "active":
                raise Model2ConflictError("A paused account profile cannot have an active niche assignment")
            if niche["status"] != "active":
                raise Model2ConflictError("An archived niche cannot have an active assignment")
            if not pinterest_account_is_connected_in_transaction(conn, assignment.account_id):
                raise Model2AccountNotConnectedError(
                    "Pinterest account must be connected before activating a niche assignment"
                )

        if assignment.is_primary and assignment.status == "active":
            # Profile row lock serializes all assignment writers for this account.
            # READ COMMITTED sees the preceding writer's commit after lock wait;
            # REPEATABLE READ may raise 40001 and the caller must retry.
            conn.execute(
                """
                UPDATE model2_account_niches
                SET is_primary = FALSE, updated_at = now()
                WHERE account_id = %s
                  AND niche_id <> %s
                  AND is_primary = TRUE
                  AND status = 'active'
                """,
                (assignment.account_id, assignment.niche_id),
            )

        row = conn.execute(
            """
            INSERT INTO model2_account_niches
                (account_id, niche_id, is_primary, status, settings)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (account_id, niche_id) DO UPDATE SET
                is_primary = EXCLUDED.is_primary,
                status = EXCLUDED.status,
                settings = EXCLUDED.settings,
                updated_at = now()
            RETURNING account_id, niche_id, is_primary, status, settings,
                      created_at, updated_at
            """,
            (assignment.account_id, assignment.niche_id, assignment.is_primary,
             assignment.status, "{}"),
        ).fetchone()
        return dict(row)


def list_account_niche_assignments(account_id: str) -> list[dict]:
    account_id = AccountProfileInput(account_id=account_id).account_id
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT account_id, niche_id, is_primary, status, settings, created_at, updated_at
            FROM model2_account_niches
            WHERE account_id = %s
            ORDER BY is_primary DESC, niche_id
            """,
            (account_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_active_account_niche_context(account_id: str, niche_id: int) -> dict:
    """Return one exact active account+niche prompt context; never infer a niche."""
    account_id = AccountProfileInput(account_id=account_id).account_id
    if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
        raise ValueError("niche_id must be a positive integer")

    with connection() as conn:
        row = conn.execute(
            """
            SELECT ap.status AS account_status,
                   an.status AS assignment_status,
                   n.status AS niche_status,
                   n.id AS niche_id,
                   n.slug,
                   n.display_name,
                   n.description,
                   n.default_region
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

    if row is None:
        raise Model2NotFoundError("Account niche assignment does not exist")
    if (
        row["account_status"] != "active"
        or row["assignment_status"] != "active"
        or row["niche_status"] != "active"
    ):
        raise Model2ConflictError("Account profile, niche assignment and niche must all be active")

    return {
        "niche_id": row["niche_id"],
        "slug": row["slug"],
        "display_name": row["display_name"],
        "description": row["description"],
        "default_region": row["default_region"],
    }
