"""Regression tests for scheduler account-to-schedule-to-job lock ordering."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app import affiliate_scheduler


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Model2LockConnection:
    def __init__(self, *, job_status="processing", stale=True):
        self.statements = []
        self.job_status = job_status
        self.stale = stale

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.statements.append(normalized)
        if "SELECT j.id FROM affiliate_pin_jobs j" in normalized:
            return Result({"id": 71})
        if "SELECT j.id AS job_id" in normalized:
            return Result({
                "job_id": 71, "schedule_id": 19,
                "account_id": "pinterest:123", "niche_id": 5,
            })
        if "FROM model2_account_profiles" in normalized:
            return Result({"account_id": "pinterest:123"})
        if "FROM model2_niches" in normalized:
            return Result({"id": 5})
        if "FROM model2_account_niches" in normalized:
            return Result({"account_id": "pinterest:123", "niche_id": 5})
        if "FROM affiliate_publishing_schedules" in normalized and "FOR UPDATE" in normalized:
            return Result({
                "id": 19, "account_id": "pinterest:123",
                "niche_id": 5, "status": "active",
            })
        if "FROM affiliate_pin_jobs" in normalized and "FOR UPDATE" in normalized:
            return Result({
                "id": 71, "schedule_id": 19, "status": self.job_status,
                "locked_at": datetime.now(timezone.utc) - timedelta(hours=1),
            })
        if "SELECT %s < now()" in normalized:
            return Result({"is_stale": self.stale})
        if normalized.startswith("UPDATE affiliate_pin_jobs"):
            return Result({"id": 71})
        return Result()


def _install_connection(monkeypatch, fake):
    @contextmanager
    def connection():
        yield fake

    monkeypatch.setattr(affiliate_scheduler, "connection", connection)


def _index(statements, fragment):
    return next(i for i, statement in enumerate(statements) if fragment in statement)


def test_finalize_claimed_job_locks_account_context_before_schedule_and_job(monkeypatch):
    fake = Model2LockConnection()
    _install_connection(monkeypatch, fake)

    assert affiliate_scheduler._finalize_claimed_job(
        {"id": 71}, status="succeeded", product_id=901,
        pinterest_pin_id="synthetic-pin-901",
    )

    profile = _index(fake.statements, "FROM model2_account_profiles")
    niche = _index(fake.statements, "FROM model2_niches")
    assignment = _index(fake.statements, "FROM model2_account_niches")
    schedule = _index(fake.statements, "FROM affiliate_publishing_schedules WHERE id = %s FOR UPDATE")
    job = _index(fake.statements, "FROM affiliate_pin_jobs WHERE id = %s FOR UPDATE")
    update = _index(fake.statements, "UPDATE affiliate_pin_jobs")
    assert profile < niche < assignment < schedule < job < update
    assert any("UPDATE affiliate_publishing_schedules" in s for s in fake.statements)


def test_stale_claim_quarantine_locks_account_context_before_job_update(monkeypatch):
    fake = Model2LockConnection(stale=True)
    _install_connection(monkeypatch, fake)

    assert affiliate_scheduler._quarantine_one_expired_claim() == 71

    profile = _index(fake.statements, "FROM model2_account_profiles")
    niche = _index(fake.statements, "FROM model2_niches")
    assignment = _index(fake.statements, "FROM model2_account_niches")
    schedule = _index(fake.statements, "FROM affiliate_publishing_schedules")
    job = _index(fake.statements, "FROM affiliate_pin_jobs j WHERE j.id")
    update = _index(fake.statements, "UPDATE affiliate_pin_jobs")
    assert profile < niche < assignment < schedule < job < update


def test_stale_claim_quarantine_rechecks_status_and_age_under_lock(monkeypatch):
    fake = Model2LockConnection(job_status="succeeded", stale=True)
    _install_connection(monkeypatch, fake)

    assert affiliate_scheduler._quarantine_one_expired_claim() is None
    assert not any(s.startswith("UPDATE affiliate_pin_jobs") for s in fake.statements)


def test_stale_claim_quarantine_does_not_change_a_recent_claim(monkeypatch):
    fake = Model2LockConnection(job_status="processing", stale=False)
    _install_connection(monkeypatch, fake)

    assert affiliate_scheduler._quarantine_one_expired_claim() is None
    assert not any(s.startswith("UPDATE affiliate_pin_jobs") for s in fake.statements)


def test_finalizer_refuses_to_overwrite_a_job_no_longer_processing(monkeypatch):
    fake = Model2LockConnection(job_status="uncertain")
    _install_connection(monkeypatch, fake)

    assert not affiliate_scheduler._finalize_claimed_job(
        {"id": 71}, status="succeeded", product_id=901,
        pinterest_pin_id="synthetic-pin-901",
    )
    assert not any(s.startswith("UPDATE affiliate_pin_jobs") for s in fake.statements)
