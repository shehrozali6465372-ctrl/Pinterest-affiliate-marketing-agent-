"""Behavioral tests for redacted GitHub Actions production summaries."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_SCRIPT = ROOT / "scripts" / "workflow_summary.py"


def _run_summary(
    tmp_path: Path,
    kind: str,
    payload: dict[str, object],
    *,
    expected_exit: int = 0,
) -> dict[str, object]:
    response_file = tmp_path / "response.json"
    response_file.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SUMMARY_SCRIPT), kind, str(response_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected_exit, result.stderr
    return json.loads(result.stdout)


def test_scheduler_summary_reports_publication_outcome_without_pin_or_affiliate_data(tmp_path):
    summary = _run_summary(
        tmp_path,
        "scheduler",
        {
            "claimed": True,
            "processed": True,
            "job_id": 14,
            "status": "succeeded",
            "published": True,
            "already_published": False,
            "pin_id": "private-pin-id",
            "affiliate_url": "https://affiliate.example/private-tag",
        },
    )

    assert summary == {
        "claimed": True,
        "processed": True,
        "job_id": 14,
        "status": "succeeded",
        "reason": None,
        "http_status": None,
        "published": True,
        "already_published": False,
    }
    rendered = json.dumps(summary)
    assert "private-pin-id" not in rendered
    assert "private-tag" not in rendered


def test_scheduler_summary_keeps_unknown_publication_outcome_unknown(tmp_path):
    summary = _run_summary(
        tmp_path,
        "scheduler",
        {"claimed": False, "processed": False, "reason": "no_due_job"},
    )

    assert summary["published"] is None
    assert summary["already_published"] is None


def test_learning_summary_reports_aggregated_failure_reasons_without_pin_identifiers(tmp_path):
    summary = _run_summary(
        tmp_path,
        "learning",
        {
            "ok": False,
            "pins_checked": 3,
            "snapshots_saved": 1,
            "period": {"start": "2026-10-10", "end": "2026-11-09"},
            "aggregate_metrics": {"impressions": 100, "outbound_clicks": 4},
            "learning_status": "analytics_ingested_descriptive_evaluation_only",
            "model_trained": False,
            "pin_results": [
                {"pin_id": "private-pin-1", "ok": True, "metrics": {"impression": 100}},
                {"pin_id": "private-pin-2", "ok": False, "failure_stage": "pinterest_http_error", "http_status": 429},
                {"pin_id": "private-pin-3", "ok": False, "failure_stage": "pinterest_timeout"},
            ],
            "access_token": "never-log-this",
        },
        expected_exit=1,
    )

    assert summary == {
        "ok": False,
        "pins_checked": 3,
        "snapshots_saved": 1,
        "period": {"start": "2026-10-10", "end": "2026-11-09"},
        "aggregate_metrics": {"impressions": 100, "outbound_clicks": 4},
        "learning_status": "analytics_ingested_descriptive_evaluation_only",
        "model_trained": False,
        "failure_count": 2,
        "failure_stages": {"pinterest_http_error": 1, "pinterest_timeout": 1},
        "failure_http_statuses": {"429": 1},
    }
    rendered = json.dumps(summary)
    assert "private-pin-" not in rendered
    assert "never-log-this" not in rendered


def test_learning_summary_does_not_invent_zero_failures_when_pin_results_are_missing(tmp_path):
    summary = _run_summary(
        tmp_path,
        "learning",
        {"ok": False, "pins_checked": 5, "snapshots_saved": 4},
        expected_exit=1,
    )

    assert summary["failure_count"] is None
    assert summary["failure_stages"] == {}
    assert summary["failure_http_statuses"] == {}


def test_successful_learning_summary_exits_zero(tmp_path):
    summary = _run_summary(
        tmp_path,
        "learning",
        {"ok": True, "pins_checked": 0, "snapshots_saved": 0, "pin_results": []},
    )

    assert summary["ok"] is True
    assert summary["failure_count"] == 0
