"""Emit bounded, secret-safe summaries for scheduled production workflows."""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


_SAFE_LABEL = re.compile(r"^[a-zA-Z0-9_]{1,80}$")
_AGGREGATE_METRICS = (
    "impressions",
    "saves",
    "outbound_clicks",
    "save_rate",
    "outbound_click_rate",
)


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("workflow response must be a JSON object")
    return value


def _boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _integer(value: object, *, minimum: int = 0, maximum: int | None = None) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _label(value: object) -> str | None:
    if isinstance(value, str) and _SAFE_LABEL.fullmatch(value):
        return value
    return None


def _period(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, str] = {}
    for key in ("start", "end"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            try:
                parsed = date.fromisoformat(candidate)
            except ValueError:
                continue
            if parsed.isoformat() == candidate:
                result[key] = candidate
    return result or None


def _aggregate_metrics(value: object) -> dict[str, int | float | None] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, int | float | None] = {}
    for key in _AGGREGATE_METRICS:
        candidate = value.get(key)
        if candidate is None:
            if key in value:
                result[key] = None
        elif (
            isinstance(candidate, (int, float))
            and not isinstance(candidate, bool)
            and (isinstance(candidate, int) or math.isfinite(candidate))
            and candidate >= 0
        ):
            result[key] = candidate
    return result or None


def scheduler_summary(response: object) -> dict[str, object]:
    """Expose the publication outcome, never Pin identifiers or affiliate URLs."""
    body = _mapping(response)
    return {
        "claimed": _boolean(body.get("claimed")),
        "processed": _boolean(body.get("processed")),
        "job_id": _integer(body.get("job_id"), minimum=1),
        "status": _label(body.get("status")),
        "reason": _label(body.get("reason")),
        "http_status": _integer(body.get("http_status"), minimum=100, maximum=599),
        "published": _boolean(body.get("published")),
        "already_published": _boolean(body.get("already_published")),
    }


def learning_summary(response: object) -> dict[str, object]:
    """Aggregate failure metadata without logging Pin IDs or per-Pin payloads."""
    body = _mapping(response)
    pin_results = body.get("pin_results")
    failure_count: int | None = None
    failure_stages: Counter[str] = Counter()
    failure_http_statuses: Counter[str] = Counter()

    if pin_results is not None:
        if not isinstance(pin_results, list):
            raise ValueError("pin_results must be a JSON array")
        failures: list[dict[str, Any]] = []
        for item in pin_results:
            result = _mapping(item)
            if result.get("ok") is False:
                failures.append(result)
        failure_count = len(failures)
        for failure in failures:
            stage = _label(failure.get("failure_stage"))
            if stage:
                failure_stages[stage] += 1
            status = _integer(failure.get("http_status"), minimum=100, maximum=599)
            if status is not None:
                failure_http_statuses[str(status)] += 1

    return {
        "ok": _boolean(body.get("ok")),
        "pins_checked": _integer(body.get("pins_checked")),
        "snapshots_saved": _integer(body.get("snapshots_saved")),
        "period": _period(body.get("period")),
        "aggregate_metrics": _aggregate_metrics(body.get("aggregate_metrics")),
        "learning_status": _label(body.get("learning_status")),
        "model_trained": _boolean(body.get("model_trained")),
        "failure_count": failure_count,
        "failure_stages": dict(sorted(failure_stages.items())),
        "failure_http_statuses": dict(sorted(failure_http_statuses.items())),
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in {"scheduler", "learning"}:
        print("usage: workflow_summary.py scheduler|learning RESPONSE_JSON", file=sys.stderr)
        return 2
    try:
        with Path(args[1]).open(encoding="utf-8") as stream:
            response = json.load(stream)
        summary = scheduler_summary(response) if args[0] == "scheduler" else learning_summary(response)
    except (OSError, json.JSONDecodeError, ValueError):
        print("workflow response could not be summarized safely", file=sys.stderr)
        return 2
    print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
    if args[0] == "learning" and summary["ok"] is not True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
