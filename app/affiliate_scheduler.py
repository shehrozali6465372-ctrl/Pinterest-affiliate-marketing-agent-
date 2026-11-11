"""Draft-first affiliate URL schedule management.

This module only stores sources and enqueues jobs. It never calls Pinterest.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.auth import require_api_key
from app.database import connection
from app.model2_domain import AccountId

router = APIRouter(prefix="/affiliate-scheduler", tags=["affiliate-scheduler"])
DEFAULT_POSTING_TIMES = (time(9, 0), time(12, 0), time(15, 0), time(18, 0), time(21, 0))

def _complete_schedule_if_terminal(conn, schedule_id: int) -> None:
    conn.execute(
        """
        UPDATE affiliate_publishing_schedules s
        SET status = 'completed', updated_at = now()
        WHERE s.id = %s AND s.status = 'active'
          AND NOT EXISTS (
            SELECT 1 FROM affiliate_pin_jobs j
            WHERE j.schedule_id = s.id AND j.status IN ('queued', 'processing', 'uncertain')
          )
        """,
        (schedule_id,),
    )


def _lock_scheduler_job_context(conn, job_id: int):
    """Lock account context before schedule/job rows; return a revalidated job snapshot."""
    hint = conn.execute(
        """
        SELECT j.id AS job_id, j.schedule_id, s.account_id, s.niche_id
        FROM affiliate_pin_jobs j
        JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
        WHERE j.id = %s
        """,
        (job_id,),
    ).fetchone()
    if not hint:
        return None

    if hint["niche_id"] is not None:
        profile = conn.execute(
            "SELECT account_id FROM model2_account_profiles WHERE account_id = %s FOR UPDATE",
            (hint["account_id"],),
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
            (hint["account_id"], hint["niche_id"]),
        ).fetchone()
        # Broken Model 2 linkage is not permission to fall back to a weaker lock order.
        if not profile or not niche or not assignment:
            return None

    schedule = conn.execute(
        """
        SELECT id, account_id, niche_id, status
        FROM affiliate_publishing_schedules
        WHERE id = %s FOR UPDATE
        """,
        (hint["schedule_id"],),
    ).fetchone()
    if (
        not schedule
        or schedule["account_id"] != hint["account_id"]
        or schedule["niche_id"] != hint["niche_id"]
    ):
        return None

    job = conn.execute(
        """
        SELECT id, schedule_id, status, locked_at
        FROM affiliate_pin_jobs
        WHERE id = %s FOR UPDATE
        """,
        (job_id,),
    ).fetchone()
    if not job or job["schedule_id"] != schedule["id"]:
        return None
    return {"schedule": schedule, "job": job}


def _quarantine_one_expired_claim() -> int | None:
    """Mark one stale processing claim uncertain while following account→schedule→job locks."""
    with connection() as conn:
        hint = conn.execute(
            """
            SELECT j.id
            FROM affiliate_pin_jobs j
            WHERE j.status = 'processing'
              AND j.locked_at < now() - interval '15 minutes'
            ORDER BY j.locked_at, j.id
            LIMIT 1
            """
        ).fetchone()
        if not hint:
            return None
        locked = _lock_scheduler_job_context(conn, hint["id"])
        if not locked:
            return None
        job = locked["job"]
        if job["status"] != "processing" or job["locked_at"] is None:
            return None
        stale = conn.execute(
            "SELECT %s < now() - interval '15 minutes' AS is_stale",
            (job["locked_at"],),
        ).fetchone()["is_stale"]
        if not stale:
            return None
        updated = conn.execute(
            """
            UPDATE affiliate_pin_jobs
            SET status = 'uncertain', finished_at = now(),
                safe_error_code = 'worker_claim_expired'
            WHERE id = %s AND status = 'processing'
            RETURNING id
            """,
            (job["id"],),
        ).fetchone()
        return updated["id"] if updated else None


def _finalize_claimed_job(
    claimed: dict[str, object],
    *,
    status: str,
    safe_error_code: str | None = None,
    delay_minutes: int | None = None,
    product_id: int | None = None,
    pinterest_pin_id: str | None = None,
) -> bool:
    """Finalize a claimed job under the same account→schedule→job lock order as reconciliation."""
    if status not in {"queued", "succeeded", "failed", "uncertain"}:
        raise ValueError("unsupported scheduler job finalization state")
    with connection() as conn:
        locked = _lock_scheduler_job_context(conn, int(claimed["id"]))
        if not locked or locked["job"]["status"] != "processing":
            return False
        if status == "queued":
            if delay_minutes is None or delay_minutes < 0:
                raise ValueError("retry delay is required")
            updated = conn.execute(
                """
                UPDATE affiliate_pin_jobs
                SET status = 'queued', locked_at = NULL,
                    run_at = now() + (%s * interval '1 minute'),
                    safe_error_code = %s
                WHERE id = %s AND status = 'processing'
                RETURNING id
                """,
                (delay_minutes, safe_error_code, int(claimed["id"])),
            ).fetchone()
        else:
            updated = conn.execute(
                """
                UPDATE affiliate_pin_jobs
                SET status = %s, finished_at = now(), product_id = %s,
                    pinterest_pin_id = %s, safe_error_code = %s
                WHERE id = %s AND status = 'processing'
                RETURNING id
                """,
                (status, product_id, pinterest_pin_id, safe_error_code, int(claimed["id"])),
            ).fetchone()
            if updated:
                _complete_schedule_if_terminal(conn, locked["schedule"]["id"])
        return bool(updated)




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
    niche_id: int | None = Field(default=None, gt=0, strict=True)
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


def _validate_model2_schedule_context(conn, *, account_id: str, niche_id: int, timezone_name: str) -> None:
    """Validate exact account+niche state using metadata only; never read token bytes."""
    try:
        AccountId(value=account_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Model 2 schedules require a canonical pinterest:<user_id> account_id.") from None

    profile = conn.execute(
        "SELECT status, timezone FROM model2_account_profiles WHERE account_id = %s FOR UPDATE",
        (account_id,),
    ).fetchone()
    if not profile or profile["status"] != "active":
        raise HTTPException(status_code=409, detail="An active Model 2 account profile is required.")
    if profile["timezone"] != timezone_name:
        raise HTTPException(status_code=409, detail="Schedule timezone must match the account profile timezone.")

    niche = conn.execute(
        "SELECT status FROM model2_niches WHERE id = %s FOR SHARE",
        (niche_id,),
    ).fetchone()
    if not niche or niche["status"] != "active":
        raise HTTPException(status_code=409, detail="The selected niche does not exist or is archived.")

    assignment = conn.execute(
        """
        SELECT status FROM model2_account_niches
        WHERE account_id = %s AND niche_id = %s
        FOR SHARE
        """,
        (account_id, niche_id),
    ).fetchone()
    if not assignment or assignment["status"] != "active":
        raise HTTPException(status_code=409, detail="The exact account-to-niche assignment is missing or inactive.")

    from app.credential_vault import pinterest_account_is_connected_in_transaction

    if not pinterest_account_is_connected_in_transaction(conn, account_id):
        raise HTTPException(status_code=409, detail="A connected Pinterest credential with matching account identity is required; no token was read or refreshed.")
    return profile["timezone"]


@router.post("/schedules", status_code=201, dependencies=[Depends(require_api_key)])
def create_draft_schedule(payload: CreateScheduleInput) -> dict[str, object]:
    """Store up to ten URLs as a draft; no jobs are queued and nothing is published."""
    if payload.starts_on < datetime.now(ZoneInfo(payload.timezone)).date():
        raise HTTPException(status_code=422, detail="starts_on cannot be earlier than today in the selected timezone.")
    ends_on = payload.starts_on + timedelta(days=payload.days - 1)
    try:
        with connection() as conn:
            if payload.niche_id is not None:
                _validate_model2_schedule_context(
                    conn, account_id=payload.account_id, niche_id=payload.niche_id,
                    timezone_name=payload.timezone,
                )
            schedule = conn.execute(
                """
                INSERT INTO affiliate_publishing_schedules
                    (account_id, niche_id, timezone, starts_on, ends_on, daily_pin_limit, board_name, board_description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft')
                RETURNING id, account_id, niche_id, timezone, starts_on, ends_on, daily_pin_limit, board_name, status
                """,
                (payload.account_id, payload.niche_id, payload.timezone, payload.starts_on, ends_on,
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
            "timezone": schedule["timezone"], "niche_id": schedule["niche_id"],
            "daily_pin_limit": schedule["daily_pin_limit"],
            "source_count": len(payload.sources), "jobs_created": 0,
            "publishing_started": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not persist the draft schedule.") from exc


@router.post("/schedules/{schedule_id}/activate", dependencies=[Depends(require_api_key)])
def activate_schedule(schedule_id: int) -> dict[str, object]:
    """Explicitly enqueue a draft schedule. This does not execute jobs or contact Pinterest."""
    try:
        with connection() as conn:
            hint = conn.execute(
                "SELECT account_id, niche_id FROM affiliate_publishing_schedules WHERE id = %s",
                (schedule_id,),
            ).fetchone()
            if not hint:
                raise HTTPException(status_code=404, detail="Schedule not found.")

            # Global Model 2 lock order: account profile -> niche -> assignment -> schedule -> jobs.
            profile_timezone = None
            if hint["niche_id"] is not None:
                schedule_timezone = conn.execute(
                    "SELECT timezone FROM affiliate_publishing_schedules WHERE id = %s",
                    (schedule_id,),
                ).fetchone()["timezone"]
                profile_timezone = _validate_model2_schedule_context(
                    conn, account_id=hint["account_id"], niche_id=hint["niche_id"],
                    timezone_name=schedule_timezone,
                )

            schedule = conn.execute(
                "SELECT * FROM affiliate_publishing_schedules WHERE id = %s FOR UPDATE",
                (schedule_id,),
            ).fetchone()
            if not schedule:
                raise HTTPException(status_code=404, detail="Schedule not found.")
            if schedule["account_id"] != hint["account_id"] or schedule["niche_id"] != hint["niche_id"]:
                raise HTTPException(status_code=409, detail="Draft schedule context changed during activation; retry after review.")
            if schedule["status"] != "draft":
                raise HTTPException(status_code=409, detail="Only a draft schedule can be activated.")
            if profile_timezone is not None and schedule["timezone"] != profile_timezone:
                raise HTTPException(status_code=409, detail="Schedule timezone must match the account profile timezone.")

            if schedule["niche_id"] is not None:
                outstanding = conn.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM affiliate_pin_jobs j
                        JOIN affiliate_publishing_schedules old_s ON old_s.id = j.schedule_id
                        WHERE old_s.account_id = %s AND old_s.id <> %s
                          AND j.status IN ('queued', 'processing', 'uncertain')
                    ) AS has_outstanding
                    """,
                    (schedule["account_id"], schedule_id),
                ).fetchone()["has_outstanding"]
                if outstanding:
                    raise HTTPException(
                        status_code=409,
                        detail="A previous schedule has queued, processing, or uncertain jobs. Wait for in-flight work and reconcile uncertain publication outcomes before replacing it.",
                    )
                active = conn.execute(
                    """
                    SELECT id FROM affiliate_publishing_schedules
                    WHERE account_id = %s AND status = 'active' AND id <> %s
                    """,
                    (schedule["account_id"], schedule_id),
                ).fetchone()
                if active:
                    raise HTTPException(status_code=409, detail="This Pinterest account already has an active schedule.")

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
            "schedule_id": schedule_id, "status": "active", "niche_id": schedule["niche_id"],
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


@router.post("/schedules/{schedule_id}/pause", dependencies=[Depends(require_api_key)])
def pause_schedule(schedule_id: int) -> dict[str, object]:
    try:
        with connection() as conn:
            hint = conn.execute(
                "SELECT account_id, niche_id FROM affiliate_publishing_schedules WHERE id = %s",
                (schedule_id,),
            ).fetchone()
            if not hint:
                raise HTTPException(status_code=409, detail="Schedule not found or not active.")
            if hint["niche_id"] is not None:
                profile = conn.execute(
                    "SELECT account_id FROM model2_account_profiles WHERE account_id = %s FOR UPDATE",
                    (hint["account_id"],),
                ).fetchone()
                if not profile:
                    raise HTTPException(status_code=409, detail="Model 2 account profile is unavailable.")
            schedule = conn.execute(
                "SELECT id, status FROM affiliate_publishing_schedules WHERE id = %s FOR UPDATE",
                (schedule_id,),
            ).fetchone()
            if not schedule or schedule["status"] != "active":
                raise HTTPException(status_code=409, detail="Schedule not found or not active.")
            conn.execute(
                "UPDATE affiliate_publishing_schedules SET status = 'paused', updated_at = now() WHERE id = %s",
                (schedule_id,),
            )
            conn.execute(
                "UPDATE affiliate_pin_jobs SET status = 'cancelled' WHERE schedule_id = %s AND status = 'queued'",
                (schedule_id,),
            )
        return {"schedule_id": schedule_id, "status": "paused", "queued_jobs_cancelled": True, "in_flight_job_may_finish": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not pause the schedule.") from exc


def _account_local_day_bounds(timezone_name: str, *, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return DST-aware UTC bounds for the current account-local calendar day."""
    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone) if now is not None else datetime.now(zone)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=zone)
    local_end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=zone)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


@router.post("/run-due", dependencies=[Depends(require_api_key)])
def run_one_due_job() -> dict[str, object]:
    """Claim and execute at most one due job. Never replays uncertain Pinterest writes."""
    from fastapi import HTTPException
    from app.workflow import ProductWorkflowInput, publish_product_end_to_end

    try:
        # Recover stale claims in a separate transaction. Bulk job/schedule
        # updates here would acquire child locks before the account-profile lock
        # used by reconciliation and could deadlock with it.
        _quarantine_one_expired_claim()
        with connection() as conn:
            # Lock a Model 2 account profile during candidate discovery. SKIP
            # LOCKED lets another worker choose a different account rather than
            # queue behind a busy account whose quota may already be exhausted.
            # The lock order remains profile -> niche -> assignment -> schedule -> job.
            model2_hint = conn.execute(
                """
                SELECT s.id AS schedule_id, s.account_id, s.niche_id, s.timezone
                FROM affiliate_pin_jobs j
                JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
                JOIN model2_account_profiles ap ON ap.account_id = s.account_id
                JOIN model2_account_niches an
                  ON an.account_id = s.account_id AND an.niche_id = s.niche_id
                JOIN model2_niches n ON n.id = s.niche_id
                JOIN pinterest_credentials pc ON pc.account_id = s.account_id
                WHERE s.niche_id IS NOT NULL
                  AND j.status = 'queued' AND j.run_at <= now() AND s.status = 'active'
                  AND ap.status = 'active' AND an.status = 'active'
                  AND n.status = 'active' AND pc.status = 'connected'
                  AND (
                    SELECT count(*)
                    FROM affiliate_pin_jobs day_jobs
                    JOIN affiliate_publishing_schedules day_s ON day_s.id = day_jobs.schedule_id
                    WHERE day_s.account_id = s.account_id
                      AND day_jobs.status IN ('processing', 'succeeded', 'uncertain')
                      AND (
                        CASE
                          WHEN day_jobs.status = 'processing' THEN COALESCE(day_jobs.locked_at, day_jobs.run_at)
                          ELSE COALESCE(day_jobs.finished_at, day_jobs.run_at)
                        END AT TIME ZONE ap.timezone
                      )::date = (now() AT TIME ZONE ap.timezone)::date
                  ) < s.daily_pin_limit
                ORDER BY j.run_at, j.id
                FOR UPDATE OF ap SKIP LOCKED
                LIMIT 1
                """
            ).fetchone()

            # Legacy Model 1 schedules have no Model 2 profile/niche lock. The
            # existing one-active-schedule index means locking their schedule
            # row serializes their legacy per-schedule quota check.
            legacy_hint = None
            if not model2_hint:
                legacy_hint = conn.execute(
                    """
                    SELECT s.id AS schedule_id, s.account_id, s.niche_id, s.timezone
                    FROM affiliate_pin_jobs j
                    JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
                    WHERE s.niche_id IS NULL
                      AND j.status = 'queued' AND j.run_at <= now() AND s.status = 'active'
                      AND (
                        SELECT count(*) FROM affiliate_pin_jobs same_day
                        WHERE same_day.schedule_id = s.id
                          AND same_day.local_run_date = j.local_run_date
                          AND same_day.status IN ('processing', 'succeeded', 'uncertain')
                      ) < s.daily_pin_limit
                    ORDER BY j.run_at, j.id
                    FOR UPDATE OF s SKIP LOCKED
                    LIMIT 1
                    """
                ).fetchone()
            hint = model2_hint or legacy_hint
            if not hint:
                return {"claimed": False, "processed": False, "reason": "no_due_job"}

            profile_timezone = None
            if hint["niche_id"] is not None:
                profile_timezone = _validate_model2_schedule_context(
                    conn, account_id=hint["account_id"], niche_id=hint["niche_id"],
                    timezone_name=hint["timezone"],
                )
            schedule = conn.execute(
                "SELECT id, account_id, niche_id, timezone, daily_pin_limit, status FROM affiliate_publishing_schedules WHERE id = %s FOR UPDATE",
                (hint["schedule_id"],),
            ).fetchone()
            if not schedule or schedule["status"] != "active":
                return {"claimed": False, "processed": False, "reason": "no_due_job"}
            if profile_timezone is not None and schedule["timezone"] != profile_timezone:
                raise HTTPException(status_code=409, detail="Schedule timezone no longer matches the account profile timezone.")

            if schedule["niche_id"] is None:
                day_start = day_end = None
            else:
                database_now = conn.execute("SELECT now() AS current_time").fetchone()["current_time"]
                day_start, day_end = _account_local_day_bounds(schedule["timezone"], now=database_now)

            claimed = conn.execute(
                """
                WITH candidate AS (
                    SELECT j.id
                    FROM affiliate_pin_jobs j
                    JOIN affiliate_publishing_schedules s ON s.id = j.schedule_id
                    WHERE j.schedule_id = %s
                      AND j.status = 'queued'
                      AND j.run_at <= now()
                      AND s.status = 'active'
                      AND (
                        (s.niche_id IS NULL AND (
                            SELECT count(*) FROM affiliate_pin_jobs same_day
                            WHERE same_day.schedule_id = s.id
                              AND same_day.local_run_date = j.local_run_date
                              AND same_day.status IN ('processing', 'succeeded', 'uncertain')
                        ) < s.daily_pin_limit)
                        OR
                        (s.niche_id IS NOT NULL AND (
                            SELECT count(*)
                            FROM affiliate_pin_jobs day_jobs
                            JOIN affiliate_publishing_schedules day_s ON day_s.id = day_jobs.schedule_id
                            WHERE day_s.account_id = s.account_id
                              AND day_jobs.status IN ('processing', 'succeeded', 'uncertain')
                              AND (CASE
                                    WHEN day_jobs.status = 'processing' THEN COALESCE(day_jobs.locked_at, day_jobs.run_at)
                                    ELSE COALESCE(day_jobs.finished_at, day_jobs.run_at)
                                   END) >= %s
                              AND (CASE
                                    WHEN day_jobs.status = 'processing' THEN COALESCE(day_jobs.locked_at, day_jobs.run_at)
                                    ELSE COALESCE(day_jobs.finished_at, day_jobs.run_at)
                                   END) < %s
                        ) < s.daily_pin_limit)
                      )
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
                """,
                (schedule["id"], day_start, day_end),
            ).fetchone()
            if not claimed:
                return {"claimed": False, "processed": False, "reason": "no_due_job"}
            details = conn.execute(
                """
                SELECT s.account_id, s.niche_id, s.board_name, s.board_description,
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
                _complete_schedule_if_terminal(conn, claimed["schedule_id"])
                return {"claimed": True, "processed": False, "job_id": claimed["id"], "reason": "source_unavailable"}
        payload = ProductWorkflowInput(
            product_name=details["product_name"],
            product_details=details["product_details"],
            affiliate_url=details["affiliate_url"],
            account_id=details["account_id"],
            niche_id=details["niche_id"],
            board_name=details["board_name"],
            board_description=details["board_description"],
        )
        try:
            result = publish_product_end_to_end(
                payload,
                idempotency_key=claimed["idempotency_key"],
            )
        except HTTPException as exc:
            detail = exc.detail
            detail_code = detail.get("code") if isinstance(detail, dict) else None
            detail_message = (
                detail.get("message", "") if isinstance(detail, dict)
                else detail if isinstance(detail, str) else "workflow_rejected"
            )
            detail_lower = str(detail_message).casefold()
            definite_pre_publish_conflict = (
                exc.status_code == 409
                and detail_code in {
                    "niche_assignment_inactive",
                    "niche_account_not_connected",
                }
            )
            uncertain = (
                not definite_pre_publish_conflict
                and (
                    exc.status_code in (409, 502)
                    or "uncertain" in detail_lower
                    or "inspect" in detail_lower
                    or "safely recorded" in detail_lower
                )
            )
            retryable = exc.status_code == 503 and not uncertain and claimed["attempt_count"] < 3
            if retryable:
                delay_minutes = 5 * (2 ** (claimed["attempt_count"] - 1))
                finalized = _finalize_claimed_job(
                    claimed, status="queued", delay_minutes=delay_minutes,
                    safe_error_code="transient_workflow_failure",
                )
            else:
                finalized = _finalize_claimed_job(
                    claimed, status="uncertain" if uncertain else "failed",
                    safe_error_code=(
                        "publish_outcome_uncertain" if uncertain
                        else "pre_publish_conflict" if definite_pre_publish_conflict
                        else f"workflow_http_{exc.status_code}"
                    ),
                )
            if not finalized:
                raise HTTPException(
                    status_code=503,
                    detail="Scheduler job state could not be finalized safely. Inspect the publication ledger before retrying.",
                )
            return {
                "claimed": True, "processed": True, "job_id": claimed["id"],
                "status": "retry_queued" if retryable else ("uncertain" if uncertain else "failed"),
                "http_status": exc.status_code,
            }
        finalized = _finalize_claimed_job(
            claimed, status="succeeded", product_id=result.get("product_id"),
            pinterest_pin_id=result.get("pin_id"), safe_error_code=None,
        )
        if not finalized:
            raise HTTPException(
                status_code=503,
                detail="Pinterest outcome could not be finalized safely in the scheduler ledger. Inspect the publication ledger before retrying.",
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


@router.get("/schedules/{schedule_id}", dependencies=[Depends(require_api_key)])
def get_schedule_status(schedule_id: int) -> dict[str, object]:
    """Return schedule state and aggregate job counts without exposing affiliate URLs."""
    try:
        with connection() as conn:
            schedule = conn.execute(
                """
                SELECT id, account_id, niche_id, timezone, starts_on, ends_on, daily_pin_limit,
                       board_name, status, created_at, updated_at
                FROM affiliate_publishing_schedules WHERE id = %s
                """,
                (schedule_id,),
            ).fetchone()
            if not schedule:
                raise HTTPException(status_code=404, detail="Schedule not found.")
            sources = conn.execute(
                "SELECT count(*) AS total FROM affiliate_product_sources WHERE schedule_id = %s",
                (schedule_id,),
            ).fetchone()["total"]
            counts = conn.execute(
                """
                SELECT status, count(*) AS total
                FROM affiliate_pin_jobs WHERE schedule_id = %s
                GROUP BY status
                """,
                (schedule_id,),
            ).fetchall()
        job_counts = {row["status"]: row["total"] for row in counts}
        return {
            "schedule_id": schedule["id"], "account_id": schedule["account_id"],
            "timezone": schedule["timezone"], "niche_id": schedule["niche_id"], "starts_on": schedule["starts_on"].isoformat(),
            "ends_on": schedule["ends_on"].isoformat(), "daily_pin_limit": schedule["daily_pin_limit"],
            "board_name": schedule["board_name"], "status": schedule["status"],
            "source_count": sources, "job_counts": job_counts,
            "created_at": schedule["created_at"].isoformat(),
            "updated_at": schedule["updated_at"].isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not read schedule status.") from exc


class SchedulerJobReconciliationInput(BaseModel):
    account_id: str = Field(min_length=10, max_length=200)
    outcome: str = Field(pattern=r"^(succeeded|failed)$")
    pinterest_pin_id: str | None = Field(default=None, min_length=1, max_length=200)
    operator_evidence: str = Field(min_length=12, max_length=2000)
    confirm_pin_absent: bool = False

    @field_validator("account_id", "operator_evidence")
    @classmethod
    def clean_reconciliation_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


@router.get("/jobs/{job_id}/reconciliation", dependencies=[Depends(require_api_key)])
def inspect_scheduler_job_reconciliation(
    job_id: int, account_id: str = Query(..., min_length=10, max_length=200),
) -> dict[str, object]:
    """Read-only ledger linkage inspection. Never calls Pinterest or the workflow."""
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="job_id must be positive")
    from app.database import get_scheduler_job_reconciliation
    try:
        result = get_scheduler_job_reconciliation(job_id, account_id=account_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Scheduler reconciliation status is unavailable.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Scheduler job was not found for this account.")
    return result


@router.post("/jobs/{job_id}/reconcile", dependencies=[Depends(require_api_key)])
def reconcile_scheduler_job_endpoint(
    job_id: int, payload: SchedulerJobReconciliationInput,
) -> dict[str, object]:
    """Atomically resolve an uncertain job using operator evidence; no provider calls."""
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="job_id must be positive")
    from app.database import reconcile_scheduler_job
    try:
        return reconcile_scheduler_job(
            job_id, account_id=payload.account_id, outcome=payload.outcome,
            pinterest_pin_id=payload.pinterest_pin_id,
            operator_evidence=payload.operator_evidence,
            confirm_pin_absent=payload.confirm_pin_absent,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Scheduler job was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Scheduler job does not belong to the requested account.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Scheduler reconciliation failed atomically; inspect the job before retrying.") from exc

