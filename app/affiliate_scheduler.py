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


@router.post("/run-due", dependencies=[Depends(require_scheduler_key)])
def run_one_due_job() -> dict[str, object]:
    """Claim and execute at most one due job. Never replays uncertain Pinterest writes."""
    from fastapi import HTTPException
    from app.workflow import ProductWorkflowInput, publish_product_end_to_end

    try:
        with connection() as conn:
            # A worker crash during a Pin create has an unknown remote outcome.
            # Quarantine stale claims instead of risking a duplicate publication.
            conn.execute(
                """
                UPDATE affiliate_pin_jobs
                SET status = 'uncertain', finished_at = now(), safe_error_code = 'worker_claim_expired'
                WHERE status = 'processing' AND locked_at < now() - interval '15 minutes'
                """
            )
            claimed = conn.execute(
                """
                WITH candidate AS (
                    SELECT j.id
                    FROM affiliate_pin_jobs j
                    JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
                    WHERE j.status = 'queued'
                      AND j.run_at <= now()
                      AND s.status = 'active'
                      AND (
                        SELECT count(*)
                        FROM affiliate_pin_jobs day_jobs
                        WHERE day_jobs.schedule_id = j.schedule_id
                          AND day_jobs.local_run_date = j.local_run_date
                          AND day_jobs.status IN ('processing', 'succeeded')
                      ) < s.daily_pin_limit
                    ORDER BY j.run_at, j.id
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT 1
                )
                UPDATE affiliate_pin_jobs j
                SET status = 'processing', locked_at = now(), attempt_count = attempt_count + 1
                FROM candidate c
                WHERE j.id = c.id
                RETURNING j.id, j.schedule_id, j.idempotency_key,
                          j.attempt_count, j.source_id
                """
            ).fetchone()
            if not claimed:
                return {"claimed": False, "processed": False, "reason": "no_due_job"}
            details = conn.execute(
                """
                SELECT s.account_id, s.board_name, s.board_description,
                       p.product_name, p.product_details, p.affiliate_url
                FROM affiliate_publishing_schedules s
                JOIN affiliate_product_sources p ON p.schedule_id = s.id
                WHERE s.id = %s AND p.id = %s AND p.enabled = TRUE
                """,
                (claimed["schedule_id"], claimed["source_id"]),
            ).fetchone()
            if not details:
                conn.execute(
                    """
                    UPDATE affiliate_pin_jobs
                    SET status = 'failed', finished_at = now(), safe_error_code = 'source_unavailable'
                    WHERE id = %s
                    """,
                    (claimed["id"],),
                )
                return {"claimed": True, "processed": False, "job_id": claimed["id"], "reason": "source_unavailable"}
        payload = ProductWorkflowInput(
            product_name=details["product_name"],
            product_details=details["product_details"],
            affiliate_url=details["affiliate_url"],
            account_id=details["account_id"],
            board_name=details["board_name"],
            board_description=details["board_description"],
        )
        try:
            result = publish_product_end_to_end(
                payload,
                idempotency_key=claimed["idempotency_key"],
                x_request_id=f"affiliate-scheduler-{claimed['id']}",
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "workflow_rejected"
            detail_lower = str(detail).casefold()
            uncertain = exc.status_code in (409, 502) or "uncertain" in detail_lower or "inspect" in detail_lower or "safely recorded" in detail_lower
            retryable = exc.status_code == 503 and not uncertain and claimed["attempt_count"] < 3
            with connection() as conn:
                if retryable:
                    delay_minutes = 5 * (2 ** (claimed["attempt_count"] - 1))
                    conn.execute(
                        """
                        UPDATE affiliate_pin_jobs
                        SET status = 'queued', locked_at = NULL,
                            run_at = now() + (%s * interval '1 minute'),
                            safe_error_code = 'transient_workflow_failure'
                        WHERE id = %s AND status = 'processing'
                        """,
                        (delay_minutes, claimed["id"]),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE affiliate_pin_jobs
                        SET status = %s, finished_at = now(), safe_error_code = %s
                        WHERE id = %s AND status = 'processing'
                        """,
                        ("uncertain" if uncertain else "failed",
                         "publish_outcome_uncertain" if uncertain else f"workflow_http_{exc.status_code}",
                         claimed["id"]),
                    )
            return {
                "claimed": True, "processed": True, "job_id": claimed["id"],
                "status": "retry_queued" if retryable else ("uncertain" if uncertain else "failed"),
                "http_status": exc.status_code,
            }
        with connection() as conn:
            conn.execute(
                """
                UPDATE affiliate_pin_jobs
                SET status = 'succeeded', finished_at = now(), product_id = %s, pinterest_pin_id = %s,
                    safe_error_code = NULL
                WHERE id = %s AND status = 'processing'
                """,
                (result.get("product_id"), result.get("pin_id"), claimed["id"]),
            )
        return {
            "claimed": True, "processed": True, "job_id": claimed["id"],
            "status": "succeeded", "published": bool(result.get("published")),
            "already_published": bool(result.get("already_published")),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Scheduler worker could not safely process a due job.") from exc
