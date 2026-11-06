from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.affiliate_scheduler import CreateScheduleInput, create_draft_schedule
from app.config import settings
from app.main import app


def test_schedule_input_limits_sources_to_ten():
    source = {
        "product_name": "Organizer",
        "product_details": "Kitchen drawer organizer",
        "affiliate_url": "https://example.com/item?tag=abc-20&x=a%2Fb",
    }
    with pytest.raises(ValueError):
        CreateScheduleInput(
            account_id="pinterest:123", timezone="America/New_York",
            starts_on=date(2099, 11, 5), sources=[source] * 11,
        )


def test_schedule_input_rejects_invalid_timezone():
    with pytest.raises(ValueError):
        CreateScheduleInput(
            account_id="pinterest:123", timezone="Not/A_Timezone",
            starts_on=date(2099, 11, 5),
            sources=[{
                "product_name": "Organizer",
                "product_details": "Kitchen drawer organizer",
                "affiliate_url": "https://example.com/item",
            }],
        )


def test_create_draft_preserves_affiliate_url_and_does_not_enqueue(monkeypatch):
    from app import affiliate_scheduler

    calls = []
    schedule_row = {
        "id": 71, "account_id": "pinterest:123", "timezone": "America/New_York",
        "starts_on": date(2026, 11, 5), "ends_on": date(2026, 12, 4),
        "daily_pin_limit": 5, "board_name": "Home Finds", "status": "draft",
    }

    class FakeConnection:
        def execute(self, query, params=None):
            calls.append((query, params))
            if "INSERT INTO affiliate_publishing_schedules" in query:
                return type("Result", (), {"fetchone": lambda self: schedule_row})()
            return type("Result", (), {"fetchone": lambda self: None})()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(affiliate_scheduler, "connection", fake_connection)
    url = "https://EXAMPLE.com/item?tag=abc%2D20&campaign=kitchen"
    payload = CreateScheduleInput(
        account_id="pinterest:123",
        timezone="America/New_York",
        starts_on=date(2099, 11, 5),
        sources=[{
            "product_name": "Organizer",
            "product_details": "Kitchen drawer organizer",
            "affiliate_url": url,
        }],
    )

    result = create_draft_schedule(payload)

    assert result["schedule_id"] == 71
    assert result["status"] == "draft"
    assert result["jobs_created"] == 0
    assert result["publishing_started"] is False
    source_insert = next(params for query, params in calls if "INSERT INTO affiliate_product_sources" in query)
    assert source_insert[3] == url
    assert not any("affiliate_pin_jobs" in query for query, _ in calls)


def test_scheduler_api_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "app_api_key", "scheduler-test-key")
    client = TestClient(app)
    response = client.post("/affiliate-scheduler/schedules", json={})
    assert response.status_code == 401


def test_activation_queues_150_slots_without_publishing(monkeypatch):
    from contextlib import contextmanager
    from app import affiliate_scheduler

    calls = []
    schedule = {
        "id": 9, "status": "draft", "timezone": "America/New_York",
        "starts_on": date(2026, 11, 5), "ends_on": date(2026, 12, 4),
        "daily_pin_limit": 5,
    }

    class Result:
        def __init__(self, one=None, many=None):
            self.one, self.many = one, many
        def fetchone(self):
            return self.one
        def fetchall(self):
            return self.many or []

    class FakeConnection:
        def execute(self, query, params=None):
            calls.append((query, params))
            if "SELECT * FROM affiliate_publishing_schedules" in query:
                return Result(one=schedule)
            if "SELECT id FROM affiliate_product_sources" in query:
                return Result(many=[{"id": 33}])
            return Result()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(affiliate_scheduler, "connection", fake_connection)
    result = affiliate_scheduler.activate_schedule(9)

    job_inserts = [x for x in calls if "INSERT INTO affiliate_pin_jobs" in x[0]]
    assert result["jobs_created"] == 150
    assert len(job_inserts) == 150
    assert result["status"] == "active"
    assert not any("publish_pin" in query or "/pins" in query for query, _ in calls)


def test_worker_with_no_due_jobs_does_not_invoke_publish(monkeypatch):
    from contextlib import contextmanager
    from app import affiliate_scheduler

    class Result:
        def fetchone(self):
            return None
    class FakeConnection:
        def execute(self, query, params=None):
            return Result()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    monkeypatch.setattr(affiliate_scheduler, "connection", fake_connection)
    result = affiliate_scheduler.run_one_due_job()

    assert result == {"claimed": False, "processed": False, "reason": "no_due_job"}


def test_worker_calls_workflow_with_supported_signature_without_publishing(monkeypatch):
    from contextlib import contextmanager
    from app import affiliate_scheduler, workflow

    claimed = {
        "id": 101,
        "schedule_id": 9,
        "idempotency_key": "scheduler-test-idempotency-key",
        "attempt_count": 1,
        "source_id": 33,
    }
    details = {
        "account_id": "pinterest:123",
        "board_name": "Home Finds",
        "board_description": "Kitchen organization",
        "product_name": "Organizer",
        "product_details": "Kitchen drawer organizer",
        "affiliate_url": "https://example.com/item",
    }
    workflow_calls = []

    class Result:
        def __init__(self, row=None):
            self.row = row

        def fetchone(self):
            return self.row

    class FakeConnection:
        def execute(self, query, params=None):
            if "WITH candidate AS" in query:
                return Result(claimed)
            if "SELECT s.account_id, s.board_name" in query:
                return Result(details)
            return Result()

    @contextmanager
    def fake_connection():
        yield FakeConnection()

    def fake_workflow(payload, *, idempotency_key):
        workflow_calls.append((payload, idempotency_key))
        return {
            "published": False,
            "already_published": False,
            "product_id": 501,
            "pin_id": None,
        }

    monkeypatch.setattr(affiliate_scheduler, "connection", fake_connection)
    monkeypatch.setattr(workflow, "publish_product_end_to_end", fake_workflow)

    result = affiliate_scheduler.run_one_due_job()

    assert result["status"] == "succeeded"
    assert result["published"] is False
    assert len(workflow_calls) == 1
    payload, key = workflow_calls[0]
    assert payload.product_name == "Organizer"
    assert key == claimed["idempotency_key"]
