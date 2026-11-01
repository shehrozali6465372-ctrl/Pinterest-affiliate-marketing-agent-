"""Real Pinterest analytics ingestion and evidence-based evaluation (no fabricated ML)."""
from __future__ import annotations

from datetime import date, timedelta
import hmac
import json
import math

import httpx
import psycopg
from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.credential_vault import TokenEncryptionConfigurationError, get_pinterest_credential
from app.database import DatabaseConfigurationError

router = APIRouter(prefix="/learning-loop", tags=["learning-loop"])
METRICS = ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"]


def _require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.app_api_key or not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="Valid X-API-Key header required.")


class LearningRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    period_days: int = Field(default=30, ge=1, le=90)


def _number(value: object) -> float:
    """Parse an explicitly returned metric; never turn missing/invalid data into fake zeroes."""
    if isinstance(value, dict):
        value = value.get("value", value.get("count"))
    if value is None or isinstance(value, bool):
        raise ValueError("Pinterest analytics metric is missing or invalid")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Pinterest analytics metric is missing or invalid") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("Pinterest analytics metric is outside the valid range")
    return number

def _extract_metrics(raw: dict[str, object]) -> dict[str, float | None]:
    """Keep absent Pinterest metrics unknown; only explicit numeric values become numbers."""
    summary = raw.get("summary_metrics")
    if summary is not None and not isinstance(summary, dict):
        raise ValueError("Pinterest analytics summary_metrics has an unexpected shape")

    metrics: dict[str, float | None] = {}
    for metric in METRICS:
        value = None
        if isinstance(summary, dict):
            value = summary.get(metric, summary.get(metric.lower()))
        else:
            value = raw.get(metric, raw.get(metric.lower()))
            if isinstance(value, dict):
                nested_summary = value.get("summary_metrics")
                if not isinstance(nested_summary, dict):
                    raise ValueError("Pinterest analytics response omitted summary metrics")
                value = nested_summary.get(metric, nested_summary.get(metric.lower()))
        metrics[metric.lower()] = None if value is None else _number(value)
    return metrics



@router.post("/run", dependencies=[Depends(_require_api_key)])
def run_learning_loop(payload: LearningRequest) -> dict[str, object]:
    """Fetch real analytics for confirmed Pins belonging to this account and persist snapshots."""
    from app.database import connection

    try:
        credential = get_pinterest_credential(payload.account_id)
    except LookupError:
        raise HTTPException(status_code=409, detail="Pinterest account is not connected in Neon.") from None
    except InvalidTag:
        raise HTTPException(status_code=503, detail="Stored Pinterest credential failed authenticated decryption.") from None
    except TokenEncryptionConfigurationError:
        raise HTTPException(status_code=503, detail="Pinterest token encryption is not configured correctly.") from None
    except DatabaseConfigurationError:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured correctly.") from None
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Credential database query failed.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Stored Pinterest credential lookup failed.") from None

    today = date.today()
    start = today - timedelta(days=payload.period_days)
    try:
        with connection() as conn:
            pins = conn.execute(
                """SELECT id AS publication_id, product_id, content_version_id, pinterest_pin_id
                   FROM pin_publications
                   WHERE status = 'succeeded' AND pinterest_pin_id IS NOT NULL AND account_id = %s
                   ORDER BY updated_at DESC""",
                (payload.account_id,),
            ).fetchall()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read confirmed publication records.") from None

    if not pins:
        return {
            "ok": True,
            "pins_checked": 0,
            "snapshots_saved": 0,
            "insights": [],
            "learning_status": "waiting_for_published_pins",
            "model_trained": False,
            "note": "No confirmed published Pins exist for this account; no metrics or training data were fabricated.",
        }

    results: list[dict[str, object]] = []
    failed = 0
    with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
        for pin in pins:
            url = f"{settings.pinterest_api_base_url.rstrip('/')}/pins/{pin['pinterest_pin_id']}/analytics"
            failure_stage = "pinterest_request"
            try:
                response = client.get(
                    url,
                    headers={"Authorization": f"Bearer {credential['access_token']}"},
                    params={
                        "start_date": start.isoformat(),
                        "end_date": today.isoformat(),
                        "metric_types": ",".join(METRICS),
                    },
                )
                if not response.is_success:
                    failed += 1
                    results.append({
                        "pin_id": pin["pinterest_pin_id"],
                        "ok": False,
                        "http_status": response.status_code,
                        "failure_stage": "pinterest_http_error",
                    })
                    continue

                failure_stage = "analytics_payload"
                body = response.json()
                raw = body.get("all", body) if isinstance(body, dict) else {}
                if not isinstance(raw, dict):
                    raise ValueError("Pinterest analytics response has an unexpected shape")

                # A missing metric is unknown, not zero. Preserve it as JSON null.
                metrics = _extract_metrics(raw)

                failure_stage = "database_persistence"
                with connection() as conn:
                    conn.execute(
                        """INSERT INTO pin_analytics_snapshots
                           (publication_id, pinterest_pin_id, period_start, period_end, metrics)
                           VALUES (%s, %s, %s, %s, %s::jsonb)
                           ON CONFLICT (pinterest_pin_id, period_start, period_end)
                           DO UPDATE SET metrics = EXCLUDED.metrics, fetched_at = now()""",
                        (
                            pin["publication_id"], pin["pinterest_pin_id"],
                            start, today, json.dumps(metrics),
                        ),
                    )
                impressions = metrics["impression"]
                outbound = metrics["outbound_click"]
                results.append({
                    "pin_id": pin["pinterest_pin_id"],
                    "ok": True,
                    "metrics": metrics,
                    "outbound_click_rate": (
                        round(outbound / impressions, 4)
                        if impressions is not None and impressions > 0 and outbound is not None
                        else None
                    ),
                })
            except httpx.TimeoutException:
                failed += 1
                results.append({"pin_id": pin["pinterest_pin_id"], "ok": False, "failure_stage": "pinterest_timeout"})
            except httpx.RequestError:
                failed += 1
                results.append({"pin_id": pin["pinterest_pin_id"], "ok": False, "failure_stage": "pinterest_transport_error"})
            except Exception:
                failed += 1
                results.append({
                    "pin_id": pin["pinterest_pin_id"],
                    "ok": False,
                    "failure_stage": failure_stage,
                })

    successful = [item for item in results if item.get("ok")]
    def aggregate(metric: str) -> float | None:
        values = [item["metrics"][metric] for item in successful]
        # A partial sum would misrepresent an aggregate when any Pin metric is unknown.
        return sum(values) if values and all(value is not None for value in values) else None

    total_impressions = aggregate("impression")
    total_saves = aggregate("save")
    total_outbound = aggregate("outbound_click")
    return {
        "ok": failed == 0,
        "pins_checked": len(pins),
        "snapshots_saved": len(successful),
        "period": {"start": start.isoformat(), "end": today.isoformat()},
        "aggregate_metrics": {
            "impressions": total_impressions,
            "saves": total_saves,
            "outbound_clicks": total_outbound,
            "save_rate": round(total_saves / total_impressions, 4) if total_impressions and total_saves is not None else None,
            "outbound_click_rate": round(total_outbound / total_impressions, 4) if total_impressions and total_outbound is not None else None,
        },
        "pin_results": results,
        "learning_status": "analytics_ingested_descriptive_evaluation_only" if successful else "analytics_unavailable",
        "model_trained": False,
        "note": "Uses live Pinterest API responses only. Predictive ML remains deferred until sufficient longitudinal data is available.",
    }
