"""Niche-scoped descriptive projections over existing raw Pin analytics."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.auth import require_api_key
from app.database import connection
from app.model2_domain import AccountId
from app.model2_repository import Model2NotFoundError

METRIC_KEYS = ("impression", "save", "pin_click", "outbound_click")

router = APIRouter(
    prefix="/model2/learning",
    tags=["model2-learning"],
    dependencies=[Depends(require_api_key)],
)


class LearningProjectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=10, max_length=200)
    niche_id: int = Field(gt=0, strict=True)
    period_start: date
    period_end: date

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, value: str) -> str:
        return AccountId(value=value).value

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        if (self.period_end - self.period_start).days > 90:
            raise ValueError("projection period must not exceed 90 days")
        return self


class LearningSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: int | None
    account_id: str
    niche_id: int
    period_start: date
    period_end: date
    metrics: dict[str, int | float | None]
    sample_size: int
    source_snapshot_count: int
    learning_status: Literal["descriptive_only", "insufficient_data"]
    created: bool = False


def _json_number(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def aggregate_source_metrics(source_metrics: list[dict[str, object]]) -> dict[str, int | float | None]:
    """Sum a metric only when every contributing raw row explicitly supplies it."""
    if not source_metrics:
        return {key: None for key in METRIC_KEYS}

    allowed = set(METRIC_KEYS)
    for source in source_metrics:
        if not isinstance(source, dict) or set(source) - allowed:
            raise ValueError("raw analytics contains unsupported metric keys")

    aggregated: dict[str, int | float | None] = {}
    for key in METRIC_KEYS:
        values = [source.get(key) for source in source_metrics]
        if any(value is None for value in values):
            aggregated[key] = None
            continue
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float, Decimal))
            for value in values
        ):
            raise ValueError(f"raw analytics metric {key} is not numeric")

        try:
            decimals = [Decimal(str(value)) for value in values]
        except (InvalidOperation, ValueError):
            raise ValueError(f"raw analytics metric {key} is not numeric") from None
        if any(not value.is_finite() or value < 0 for value in decimals):
            raise ValueError(f"raw analytics metric {key} is outside the valid range")
        aggregated[key] = _json_number(sum(decimals, Decimal("0")))

    return aggregated


def _snapshot_dict(row: dict, *, created: bool) -> dict:
    return {
        "snapshot_id": row["id"],
        "account_id": row["account_id"],
        "niche_id": row["niche_id"],
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "metrics": row["metrics"],
        "sample_size": row["sample_size"],
        "source_snapshot_count": row["source_snapshot_count"],
        "learning_status": row["learning_status"],
        "created": created,
    }


def create_learning_snapshot(
    *,
    account_id: str,
    niche_id: int,
    period_start: date,
    period_end: date,
) -> dict:
    """Materialize one immutable account+niche snapshot from exact raw period rows."""
    account_id = AccountId(value=account_id).value
    if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
        raise ValueError("niche_id must be a positive integer")
    if period_end < period_start or (period_end - period_start).days > 90:
        raise ValueError("projection period must be ordered and no longer than 90 days")

    with connection() as conn:
        mapping = conn.execute(
            """
            SELECT account_id
            FROM model2_account_niches
            WHERE account_id = %s AND niche_id = %s
            FOR SHARE
            """,
            (account_id, niche_id),
        ).fetchone()
        if mapping is None:
            raise Model2NotFoundError("Account niche assignment does not exist")

        existing = conn.execute(
            """
            SELECT id, account_id, niche_id, period_start, period_end,
                   metrics, sample_size, source_snapshot_count, learning_status
            FROM model2_learning_snapshots
            WHERE account_id = %s AND niche_id = %s
              AND period_start = %s AND period_end = %s
            """,
            (account_id, niche_id, period_start, period_end),
        ).fetchone()
        if existing is not None:
            return _snapshot_dict(existing, created=False)

        source_rows = conn.execute(
            """
            SELECT analytics.id AS analytics_snapshot_id,
                   analytics.publication_id,
                   analytics.metrics
            FROM pin_analytics_snapshots AS analytics
            JOIN pin_publications AS publication
              ON publication.id = analytics.publication_id
             AND publication.account_id = %s
             AND publication.status = 'succeeded'
             AND publication.pinterest_pin_id = analytics.pinterest_pin_id
            JOIN model2_publication_niche_attributions AS attribution
              ON attribution.publication_id = publication.id
             AND attribution.account_id = publication.account_id
             AND attribution.niche_id = %s
            WHERE analytics.period_start = %s
              AND analytics.period_end = %s
            ORDER BY analytics.publication_id, analytics.id
            FOR SHARE OF analytics, publication
            """,
            (account_id, niche_id, period_start, period_end),
        ).fetchall()

        if not source_rows:
            return {
                "snapshot_id": None,
                "account_id": account_id,
                "niche_id": niche_id,
                "period_start": period_start,
                "period_end": period_end,
                "metrics": {key: None for key in METRIC_KEYS},
                "sample_size": 0,
                "source_snapshot_count": 0,
                "learning_status": "insufficient_data",
                "created": False,
            }

        source_metrics = [row["metrics"] for row in source_rows]
        if any(not isinstance(metrics, dict) for metrics in source_metrics):
            raise ValueError("raw analytics metrics must be JSON objects")
        metrics = aggregate_source_metrics(source_metrics)
        sample_size = len({row["publication_id"] for row in source_rows})
        source_snapshot_count = len(source_rows)

        inserted = conn.execute(
            """
            INSERT INTO model2_learning_snapshots
                (account_id, niche_id, period_start, period_end, metrics,
                 sample_size, source_snapshot_count, learning_status)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'descriptive_only')
            ON CONFLICT (account_id, niche_id, period_start, period_end)
            DO NOTHING
            RETURNING id, account_id, niche_id, period_start, period_end,
                      metrics, sample_size, source_snapshot_count, learning_status
            """,
            (
                account_id, niche_id, period_start, period_end,
                json.dumps(metrics), sample_size, source_snapshot_count,
            ),
        ).fetchone()

        if inserted is None:
            # A concurrent transaction materialized the same immutable period.
            existing = conn.execute(
                """
                SELECT id, account_id, niche_id, period_start, period_end,
                       metrics, sample_size, source_snapshot_count, learning_status
                FROM model2_learning_snapshots
                WHERE account_id = %s AND niche_id = %s
                  AND period_start = %s AND period_end = %s
                """,
                (account_id, niche_id, period_start, period_end),
            ).fetchone()
            if existing is None:
                raise RuntimeError("concurrent learning snapshot reservation disappeared")
            return _snapshot_dict(existing, created=False)

        for row in source_rows:
            conn.execute(
                """
                INSERT INTO model2_learning_snapshot_sources
                    (learning_snapshot_id, analytics_snapshot_id, publication_id,
                     account_id, niche_id, source_metrics)
                VALUES (%s, %s, %s, %s, %s, '{}'::jsonb)
                """,
                (
                    inserted["id"], row["analytics_snapshot_id"],
                    row["publication_id"], account_id, niche_id,
                ),
            )

        return _snapshot_dict(inserted, created=True)


def list_learning_snapshots(*, account_id: str, niche_id: int, limit: int = 30) -> list[dict]:
    """List only snapshots belonging to the exact requested account+niche pair."""
    account_id = AccountId(value=account_id).value
    if isinstance(niche_id, bool) or not isinstance(niche_id, int) or niche_id <= 0:
        raise ValueError("niche_id must be a positive integer")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    with connection() as conn:
        mapping = conn.execute(
            """
            SELECT account_id
            FROM model2_account_niches
            WHERE account_id = %s AND niche_id = %s
            """,
            (account_id, niche_id),
        ).fetchone()
        if mapping is None:
            raise Model2NotFoundError("Account niche assignment does not exist")

        rows = conn.execute(
            """
            SELECT id, account_id, niche_id, period_start, period_end,
                   metrics, sample_size, source_snapshot_count, learning_status
            FROM model2_learning_snapshots
            WHERE account_id = %s AND niche_id = %s
            ORDER BY period_end DESC, id DESC
            LIMIT %s
            """,
            (account_id, niche_id, limit),
        ).fetchall()
    return [_snapshot_dict(row, created=False) for row in rows]


@router.post("/snapshots", response_model=LearningSnapshotResponse)
def post_learning_snapshot(payload: LearningProjectionInput) -> dict:
    try:
        return create_learning_snapshot(
            account_id=payload.account_id,
            niche_id=payload.niche_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    except Model2NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Learning projection storage is temporarily unavailable.",
        ) from None


@router.get(
    "/accounts/{account_id}/niches/{niche_id}/snapshots",
    response_model=list[LearningSnapshotResponse],
)
def get_learning_snapshots(
    account_id: str,
    niche_id: int = Path(gt=0),
    limit: int = Query(default=30, ge=1, le=100),
) -> list[dict]:
    try:
        return list_learning_snapshots(
            account_id=account_id,
            niche_id=niche_id,
            limit=limit,
        )
    except Model2NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Learning projection storage is temporarily unavailable.",
        ) from None
