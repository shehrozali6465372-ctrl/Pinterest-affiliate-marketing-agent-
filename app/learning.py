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
# Organic Pin analytics metric identifiers supported by Pinterest API v5.
# Engagements and engagement_rate are derived from the documented component metrics.
METRICS = [
    "IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK", "SAVE_RATE",
    "USER_FOLLOW", "PROFILE_VISIT",
]
AUDIENCE_TYPES = ("YOUR_TOTAL_AUDIENCE", "YOUR_ENGAGED_AUDIENCE")


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

                # Support top-level summary_metrics and per-metric wrappers.
                # Pinterest's PinAnalyticsResponse normally places period totals in
                # raw['summary_metrics']; some responses expose per-metric wrappers.
                summary = raw.get("summary_metrics")
                if summary is not None and not isinstance(summary, dict):
                    raise ValueError("Pinterest analytics summary_metrics has an unexpected shape")
                metrics: dict[str, float] = {}
                for metric in METRICS:
                    if isinstance(summary, dict):
                        # Pinterest may omit metrics with no returned data; a valid
                        # summary object with an absent requested metric means zero.
                        value = summary.get(metric, summary.get(metric.lower(), 0))
                    else:
                        value = raw.get(metric, raw.get(metric.lower()))
                        if isinstance(value, dict):
                            nested_summary = value.get("summary_metrics")
                            if not isinstance(nested_summary, dict):
                                raise ValueError("Pinterest analytics response omitted summary metrics")
                            value = nested_summary.get(metric, nested_summary.get(metric.lower(), 0))
                        elif value is None:
                            raise ValueError("Pinterest analytics response omitted a requested metric")
                    metrics[metric.lower()] = _number(value)

                impressions = metrics["impression"]
                engagements = metrics["save"] + metrics["pin_click"] + metrics["outbound_click"]
                metrics["engagements"] = engagements
                metrics["engagement_rate"] = round(engagements / impressions, 4) if impressions else None
                metrics["pin_click_rate"] = round(metrics["pin_click"] / impressions, 4) if impressions else None
                metrics["outbound_click_rate"] = round(metrics["outbound_click"] / impressions, 4) if impressions else None
                metrics["save_rate_calculated"] = round(metrics["save"] / impressions, 4) if impressions else None

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
                results.append({
                    "pin_id": pin["pinterest_pin_id"],
                    "ok": True,
                    "metrics": metrics,
                    "outbound_click_rate": metrics["outbound_click_rate"],
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
    total_impressions = sum(item["metrics"]["impression"] for item in successful)
    total_saves = sum(item["metrics"]["save"] for item in successful)
    total_outbound = sum(item["metrics"]["outbound_click"] for item in successful)
    total_pin_clicks = sum(item["metrics"]["pin_click"] for item in successful)
    total_profile_visits = sum(item["metrics"]["profile_visit"] for item in successful)
    total_follows = sum(item["metrics"]["user_follow"] for item in successful)
    total_engagements = total_saves + total_pin_clicks + total_outbound
    return {
        "ok": failed == 0,
        "pins_checked": len(pins),
        "snapshots_saved": len(successful),
        "period": {"start": start.isoformat(), "end": today.isoformat()},
        "aggregate_metrics": {
            "impressions": total_impressions,
            "saves": total_saves,
            "outbound_clicks": total_outbound,
            "pin_clicks": total_pin_clicks,
            "profile_visits": total_profile_visits,
            "follows": total_follows,
            "engagements": total_engagements,
            "engagement_rate": round(total_engagements / total_impressions, 4) if total_impressions else None,
            "pin_click_rate": round(total_pin_clicks / total_impressions, 4) if total_impressions else None,
            "save_rate": round(total_saves / total_impressions, 4) if total_impressions else None,
            "outbound_click_rate": round(total_outbound / total_impressions, 4) if total_impressions else None,
        },
        "pin_results": results,
        "learning_status": "analytics_ingested_descriptive_evaluation_only" if successful else "analytics_unavailable",
        "model_trained": False,
        "note": "Uses live Pinterest API responses only. Predictive ML remains deferred until sufficient longitudinal data is available.",
    }



def list_ad_accounts(account_id: str) -> dict[str, object]:
    """List advertiser accounts the connected Pinterest user can read."""
    credential = get_pinterest_credential(account_id)
    scopes = set(str(credential.get("scope") or "").replace(",", " ").split())
    if "ads:read" not in scopes:
        return {
            "ok": False,
            "requires_scope": "ads:read",
            "ad_accounts": [],
            "note": "Reconnect Pinterest and approve ads:read before listing advertiser accounts.",
        }

    base = settings.pinterest_api_base_url.rstrip("/")
    accounts: list[dict[str, object]] = []
    bookmark = None
    with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
        for _ in range(5):
            params: dict[str, object] = {"page_size": 250, "include_shared_accounts": "true"}
            if bookmark:
                params["bookmark"] = bookmark
            response = client.get(
                f"{base}/ad_accounts",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
                params=params,
            )
            if not response.is_success:
                return {
                    "ok": False,
                    "http_status": response.status_code,
                    "ad_accounts": [],
                    "note": "Pinterest could not return advertiser accounts. Verify ads:read and Business Access.",
                }
            body = response.json()
            items = body.get("items", []) if isinstance(body, dict) else []
            if not isinstance(items, list):
                raise ValueError("Pinterest ad account response has an unexpected shape")
            for item in items:
                if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
                    continue
                accounts.append({
                    "id": str(item["id"]),
                    "name": str(item.get("name") or ""),
                    "country": item.get("country"),
                    "currency": item.get("currency"),
                    "status": item.get("status"),
                })
            bookmark = body.get("bookmark") if isinstance(body, dict) else None
            if not bookmark:
                break
    return {"ok": True, "ad_accounts": accounts, "count": len(accounts)}


def _normalize_audience_insight(body: dict[str, object]) -> dict[str, object]:
    """Expose only aggregate Pinterest audience dimensions; never infer individual traits."""
    demographics = body.get("demographics")
    demographics = demographics if isinstance(demographics, dict) else {}

    def rows(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        normalized: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("key")
            ratio = item.get("ratio")
            try:
                percentage = float(ratio) * 100
            except (TypeError, ValueError, OverflowError):
                percentage = None
            if percentage is not None and (not math.isfinite(percentage) or percentage < 0):
                percentage = None
            normalized.append({
                "name": str(name) if name is not None else "Unspecified",
                "percentage": round(percentage, 2) if percentage is not None else None,
                "count": item.get("count") if isinstance(item.get("count"), (int, float)) else None,
            })
        return normalized

    return {
        "audience_size": body.get("size"),
        "size_is_upper_bound": body.get("size_is_upper_bound"),
        "last_updated": body.get("date"),
        "interests": rows(body.get("categories")),
        "age_groups": rows(demographics.get("ages")),
        "gender": rows(demographics.get("genders")),
        "devices": rows(demographics.get("devices")),
        "countries": rows(demographics.get("countries")),
        "cities_or_metros": rows(demographics.get("metros")),
        "location_note": "Pinterest supplies top metro areas, not exact city or street-level location.",
        "age_note": "Age is reported in aggregated age bands, not verified individual dates of birth.",
        "gender_note": "Pinterest may return Unspecified & custom; this must not be reassigned to Male or Female.",
        "device_note": "Device describes Pinterest usage device (app/web), not the original referral source.",
    }


def run_audience_insights(account_id: str, ad_account_id: str) -> dict[str, object]:
    """Fetch aggregated 30-day total and engaged audience insights; persist no PII."""
    from app.database import connection

    if not ad_account_id.isdigit() or len(ad_account_id) > 18:
        raise ValueError("ad_account_id must contain 1–18 digits")

    credential = get_pinterest_credential(account_id)
    scopes = set(str(credential.get("scope") or "").replace(",", " ").split())
    if "ads:read" not in scopes:
        return {
            "ok": False,
            "requires_scope": "ads:read",
            "audience_insights": [],
            "note": "Reconnect Pinterest and approve ads:read before requesting audience insights.",
        }

    base = settings.pinterest_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {credential['access_token']}"}
    snapshots: list[dict[str, object]] = []
    with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
        for audience_type in AUDIENCE_TYPES:
            response = client.get(
                f"{base}/ad_accounts/{ad_account_id}/audience_insights",
                headers=headers,
                params={"audience_insight_type": audience_type},
            )
            if not response.is_success:
                return {
                    "ok": False,
                    "http_status": response.status_code,
                    "audience_insights": [],
                    "note": "Pinterest denied or could not return audience insights. Verify Business account and advertiser access.",
                }
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("Pinterest audience insight response has an unexpected shape")
            snapshots.append({
                "audience_insight_type": audience_type,
                "data": body,
                "breakdown": _normalize_audience_insight(body),
            })

    today = date.today()
    period_start = today - timedelta(days=29)
    with connection() as conn:
        for snapshot in snapshots:
            conn.execute(
                """INSERT INTO pinterest_audience_insight_snapshots
                   (account_id, ad_account_id, audience_insight_type, period_start, period_end, data)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (account_id, ad_account_id, audience_insight_type, period_start, period_end)
                   DO UPDATE SET data = EXCLUDED.data, fetched_at = now()""",
                (
                    account_id, ad_account_id, snapshot["audience_insight_type"],
                    period_start, today, json.dumps(snapshot["data"]),
                ),
            )

    return {
        "ok": True,
        "ad_account_id": ad_account_id,
        "period": {"start": period_start.isoformat(), "end": today.isoformat()},
        "audience_insights": snapshots,
        "snapshots_saved": len(snapshots),
        "data_is_aggregated": True,
    }
