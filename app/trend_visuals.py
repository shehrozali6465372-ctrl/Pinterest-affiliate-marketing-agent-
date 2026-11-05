"""Pinterest featured topics and real example Pin visual metadata."""
from __future__ import annotations
from datetime import date, datetime, timezone
import json
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from app.config import settings
from app.credential_vault import get_pinterest_credential

router = APIRouter(prefix="/trend-visuals", tags=["trend-visuals"])
REGIONS = {"US": "United States", "GB+IE": "Great Britain & Ireland"}

class VisualTrendRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=200)
    regions: list[str] = Field(default_factory=lambda: ["US", "GB+IE"], min_length=1, max_length=2)

def fetch_featured_topics(account_id: str, regions: list[str]) -> dict[str, object]:
    from app.database import connection
    if len(set(regions)) != len(regions) or any(r not in REGIONS for r in regions):
        raise ValueError("Only unique supported regions US and GB+IE are accepted")
    credential = get_pinterest_credential(account_id)
    scopes = set(str(credential.get("scope") or "").replace(",", " ").split())
    if "user_accounts:read" not in scopes:
        return {"ok": False, "requires_scope": "user_accounts:read", "regions": [],
                "note": "Reconnect Pinterest and approve user_accounts:read."}
    now = datetime.now(timezone.utc)
    result = []
    with httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
        for region in regions:
            response = client.get(
                f"{settings.pinterest_api_base_url.rstrip('/')}/trends/topics/featured",
                headers={"Authorization": f"Bearer {credential['access_token']}"},
                params={"interest": "ALL", "region": region},
            )
            if not response.is_success:
                return {"ok": False, "http_status": response.status_code, "regions": result,
                        "note": "Pinterest featured topics unavailable. No visual trend was inferred."}
            body = response.json()
            entries = body if isinstance(body, list) else [body]
            topics = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for topic in entry.get("trends", []):
                    if not isinstance(topic, dict):
                        continue
                    samples = []
                    for pin in topic.get("pins", []) if isinstance(topic.get("pins"), list) else []:
                        if isinstance(pin, dict) and isinstance(pin.get("src"), str):
                            samples.append({
                                "image_url": pin["src"], "width": pin.get("width"),
                                "height": pin.get("height"), "dominant_color": pin.get("color"),
                                "vertical_offset": pin.get("vertical_offset"), "pin_id": pin.get("id")
                            })
                    topics.append({
                        "title": topic.get("title"), "description": topic.get("description"),
                        "growth_month_over_month_pct": topic.get("percent_growth_mom"),
                        "related_interests": topic.get("related_interests", []),
                        "related_searches": topic.get("related_searches", []),
                        "example_pins": samples
                    })
            result.append({"region": region, "region_name": REGIONS[region], "topics": topics})
    with connection() as conn:
        for market in result:
            conn.execute(
                """INSERT INTO pinterest_trend_snapshots
                   (account_id, region, trend_type, snapshot_date, fetched_at, data)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (account_id, region, trend_type, snapshot_date)
                   DO UPDATE SET fetched_at = EXCLUDED.fetched_at, data = EXCLUDED.data""",
                (account_id, market["region"], "featured:ALL", date.today(), now, json.dumps(market))
            )
    return {"ok": True, "source": "Pinterest Trends Featured Topics API v5",
            "fetched_at": now.isoformat(), "regions": result, "read_only": True,
            "note": "Example Pin image metadata comes from Pinterest. It is not yet a machine-vision classification."}

def require_ingest_key(x_credential_ingest_key: str | None = Header(default=None, alias="X-Credential-Ingest-Key")):
    import hmac
    expected = settings.pinterest_credential_ingest_key
    if not expected or not hmac.compare_digest(x_credential_ingest_key or "", expected):
        raise HTTPException(status_code=401, detail="Valid service credential required.")

@router.post("/run", dependencies=[Depends(require_ingest_key)])
def run_visual_trends(payload: VisualTrendRequest):
    try:
        return fetch_featured_topics(payload.account_id, payload.regions)
    except LookupError:
        raise HTTPException(status_code=404, detail="Pinterest account is not connected.") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=502, detail="Could not fetch Pinterest featured topics.") from None
