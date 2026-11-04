"""Draft-first affiliate URL schedule management.

This module only stores sources and enqueues jobs. It never calls Pinterest.
"""
from __future__ import annotations

import hmac
from datetime import date, datetime, time, timedelta
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.database import connection

router = APIRouter(prefix="/affiliate-scheduler", tags=["affiliate-scheduler"])
DEFAULT_POSTING_TIMES = (time(9, 0), time(12, 0), time(15, 0), time(18, 0), time(21, 0))


def require_scheduler_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key:
        raise HTTPException(status_code=503, detail="API authentication is not configured.")
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


class AffiliateSourceInput(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    product_details: str = Field(min_length=1, max_length=10000)
    affiliate_url: str = Field(min_length=8, max_length=4096)

    @field_validator("product_name", "product_details")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("affiliate_url")
    @classmethod
    def preserve_http_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if value != value.strip() or parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            raise ValueError("affiliate_url must be an absolute HTTP(S) URL without surrounding whitespace")
        if parts.username or parts.password:
            raise ValueError("affiliate_url must not contain embedded credentials")
        return value


class CreateScheduleInput(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    timezone: str = Field(min_length=1, max_length=100)
    starts_on: date
    days: int = Field(default=30, ge=1, le=30)
    daily_pin_limit: int = Field(default=5, ge=1, le=5)
    board_name: str = Field(default="Modern Living Hub | Kitchen & Home Organization", min_length=1, max_length=100)
    board_description: str = Field(default="Kitchen organization, practical home finds, and home decor inspiration.", max_length=500)
    sources: list[AffiliateSourceInput] = Field(min_length=1, max_length=10)

    @field_validator("account_id", "board_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("timezone must be a valid IANA timezone") from None
        return value


@router.post("/schedules", status_code=201, dependencies=[Depends(require_scheduler_key)])
def create_draft_schedule(payload: CreateScheduleInput) -> dict[str, object]:
    """Store up to ten URLs as a draft; no jobs are queued and nothing is published."""
    ends_on = payload.starts_on + timedelta(days=payload.days - 1)
    try:
        with connection() as conn:
            schedule = conn.execute(
                """
                INSERT INTO affiliate_publishing_schedules
                    (account_id, timezone, starts_on, ends_on, daily_pin_limit, board_name, board_description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft')
                RETURNING id, account_id, timezone, starts_on, ends_on, daily_pin_limit, board_name, status
                """,
                (payload.account_id, payload.timezone, payload.starts_on, ends_on,
                 payload.daily_pin_limit, payload.board_name, payload.board_description),
            ).fetchone()
            for source in payload.sources:
                conn.execute(
                    """
                    INSERT INTO affiliate_product_sources
                        (schedule_id, product_name, product_details, affiliate_url)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (schedule["id"], source.product_name, source.product_details, source.affiliate_url),
                )
        return {
            "schedule_id": schedule["id"], "status": "draft",
            "starts_on": schedule["starts_on"].isoformat(),
            "ends_on": schedule["ends_on"].isoformat(),
            "timezone": schedule["timezone"], "daily_pin_limit": schedule["daily_pin_limit"],
            "source_count": len(payload.sources), "jobs_created": 0,
            "publishing_started": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not persist the draft schedule.") from exc


@router.post("/schedules/{schedule_id}/activate", dependencies=[Depends(require_scheduler_key)])
def activate_schedule(schedule_id: int) -> dict[str, object]:
    """Explicitly enqueue a draft schedule. This does not execute jobs or contact Pinterest."""
    try:
        with connection() as conn:
            schedule = conn.execute(
                "SELECT * FROM affiliate_publishing_schedules WHERE id = %s FOR UPDATE",
                (schedule_id,),
            ).fetchone()
            if not schedule:
                raise HTTPException(status_code=404, detail="Schedule not found.")
            if schedule["status"] != "draft":
                raise HTTPException(status_code=409, detail="Only a draft schedule can be activated.")
            sources = conn.execute(
                "SELECT id FROM affiliate_product_sources WHERE schedule_id = %s AND enabled = TRUE ORDER BY id",
                (schedule_id,),
            ).fetchall()
            if not sources:
                raise HTTPException(status_code=409, detail="Schedule has no enabled product sources.")
            zone = ZoneInfo(schedule["timezone"])
            cursor = 0
            jobs_created = 0
            for day_offset in range((schedule["ends_on"] - schedule["starts_on"]).days + 1):
                local_day = schedule["starts_on"] + timedelta(days=day_offset)
                for slot_index, local_time in enumerate(DEFAULT_POSTING_TIMES[:schedule["daily_pin_limit"]], start=1):
                    source = sources[cursor % len(sources)]
                    cursor += 1
                    local_dt = datetime.combine(local_day, local_time, tzinfo=zone)
                    conn.execute(
                        """
                        INSERT INTO affiliate_pin_jobs
                            (schedule_id, source_id, run_at, local_run_date, daily_slot, idempotency_key)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (schedule_id, source["id"], local_dt.astimezone(ZoneInfo("UTC")),
                         local_day, slot_index, f"affsched-{schedule_id}-{local_day.isoformat()}-{slot_index}-{uuid4().hex}"),
                    )
                    jobs_created += 1
            conn.execute(
                "UPDATE affiliate_publishing_schedules SET status = 'active', updated_at = now() WHERE id = %s",
                (schedule_id,),
            )
        return {
            "schedule_id": schedule_id, "status": "active",
            "jobs_created": jobs_created, "daily_pin_limit": schedule["daily_pin_limit"],
            "starts_on": schedule["starts_on"].isoformat(),
            "ends_on": schedule["ends_on"].isoformat(),
            "timezone": schedule["timezone"],
            "note": "Jobs are queued only. This endpoint does not publish Pins or create Pinterest boards.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not activate and enqueue the schedule.") from exc


@router.post("/schedules/{schedule_id}/pause", dependencies=[Depends(require_scheduler_key)])
def pause_schedule(schedule_id: int) -> dict[str, object]:
    try:
        with connection() as conn:
            row = conn.execute(
                """
                UPDATE affiliate_publishing_schedules
                SET status = 'paused', updated_at = now()
                WHERE id = %s AND status = 'active'
                RETURNING id
                """,
                (schedule_id,),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="Schedule not found or not active.")
            conn.execute(
                "UPDATE affiliate_pin_jobs SET status = 'cancelled' WHERE schedule_id = %s AND status = 'queued'",
                (schedule_id,),
            )
        return {"schedule_id": schedule_id, "status": "paused", "queued_jobs_cancelled": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not pause the schedule.") from exc
