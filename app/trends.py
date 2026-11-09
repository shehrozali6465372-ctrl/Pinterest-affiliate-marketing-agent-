"""Read-only Pinterest Trends API ingestion; source values are never fabricated."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.auth import require_credential_ingest_key
from app.credential_vault import get_pinterest_credential

router = APIRouter(prefix="/trend-intelligence", tags=["trend-intelligence"])
SUPPORTED_REGIONS = {"US": "United States", "GB+IE": "Great Britain & Ireland"}
TREND_TYPE = "growing"


class TrendRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    regions: list[str] = Field(default_factory=lambda: ["US", "GB+IE"], min_length=1, max_length=2)
    limit: int = Field(default=50, ge=1, le=50)


def _normalize_trend(item: object, rank: int, region: str) -> dict[str, object]:
    if not isinstance(item, dict) or not isinstance(item.get("keyword"), str):
        raise ValueError("Pinterest returned a malformed trend item")
    series = item.get("time_series")
    if series is not None and not isinstance(series, dict):
        raise ValueError("Pinterest returned a malformed trend time series")
    return {
        "keyword": item["keyword"],
        "rank": rank,
        "region": region,
        "region_name": SUPPORTED_REGIONS[region],
        "growth_week_over_week_pct": item.get("pct_growth_wow"),
        "growth_month_over_month_pct": item.get("pct_growth_mom"),
        "growth_year_over_year_pct": item.get("pct_growth_yoy"),
        "weekly_relative_search_interest": series or {},
        "source": "Pinterest Trends API v5",
    }


def fetch_trends(account_id: str, regions: list[str], limit: int = 50) -> dict[str, object]:
    """Fetch current-day growing search terms for selected markets and persist snapshots."""
    from app.database import connection

    if len(set(regions)) != len(regions) or any(region not in SUPPORTED_REGIONS for region in regions):
        raise ValueError("Only unique supported regions US and GB+IE are accepted")
    credential = get_pinterest_credential(account_id)
    scopes = set(str(credential.get("scope") or "").replace(",", " ").split())
    if "user_accounts:read" not in scopes:
        return {
            "ok": False,
            "requires_scope": "user_accounts:read",
            "regions": [],
            "note": "Reconnect Pinterest and approve user_accounts:read to read Pinterest Trends.",
        }

    base = settings.pinterest_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {credential['access_token']}"}
    fetched_at = datetime.now(timezone.utc)
    result_regions: list[dict[str, object]] = []
    with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
        for region in regions:
            response = client.get(
                f"{base}/trends/keywords/{region}/top/{TREND_TYPE}",
                headers=headers,
                params={"limit": limit},
            )
            if not response.is_success:
                return {
                    "ok": False,
                    "http_status": response.status_code,
                    "regions": result_regions,
                    "note": "Pinterest Trends API did not return data. Check app/API access and retry later; no trend was inferred.",
                }
            body = response.json()
            items = body.get("trends") if isinstance(body, dict) else None
            if not isinstance(items, list):
                raise ValueError("Pinterest Trends response omitted its trends list")
            trends = [_normalize_trend(item, index + 1, region) for index, item in enumerate(items)]
            result_regions.append({"region": region, "region_name": SUPPORTED_REGIONS[region], "trends": trends})

    with connection() as conn:
        for region_result in result_regions:
            conn.execute(
                """INSERT INTO pinterest_trend_snapshots
                   (account_id, region, trend_type, snapshot_date, fetched_at, data)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (account_id, region, trend_type, snapshot_date)
                   DO UPDATE SET fetched_at = EXCLUDED.fetched_at, data = EXCLUDED.data""",
                (account_id, region_result["region"], TREND_TYPE, date.today(), fetched_at, json.dumps(region_result)),
            )

    return {
        "ok": True,
        "source": "Pinterest Trends API v5",
        "trend_type": TREND_TYPE,
        "fetched_at": fetched_at.isoformat(),
        "snapshot_date": date.today().isoformat(),
        "regions": result_regions,
        "limits": {
            "max_results_per_region": 50,
            "historical_api_dates_available": False,
            "note": "Pinterest's API returns current-date trends only. Saved snapshots build our own history from the date ingestion starts.",
        },
        "read_only": True,
    }


@router.post("/run", dependencies=[Depends(require_credential_ingest_key)])
def run_trend_intelligence(payload: TrendRequest) -> dict[str, object]:
    try:
        return fetch_trends(payload.account_id, payload.regions, payload.limit)
    except LookupError:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="Could not fetch or persist Pinterest trend data.") from None
