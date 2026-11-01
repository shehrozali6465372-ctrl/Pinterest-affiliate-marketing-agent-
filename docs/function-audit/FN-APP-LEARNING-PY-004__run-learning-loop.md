# run_learning_loop

- **Unique ID:** `FN-APP-LEARNING-PY-004`
- **Source:** `app/learning.py:49-203`
- **Snapshot:** `main @ 336d8bcd793843e4c3bb0aa626005fc6b82f0ef0`
- **Status:** `UNVERIFIED`

## Analysis

This function is the Learning Loop entry point. Its actual behavior must be distinguished from predictive ML: verify API calls, metrics, persistence, cohort/time-window handling, and whether training occurs.

## Source excerpt

```python
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
                results.append({
                    "pin_id": pin["pinterest_pin_id"],
                    "ok": True,
                    "metrics": metrics,
                    "outbound_click_rate": round(metrics["outbound_click"] / impressions, 4) if impressions else None,
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
    return {
        "ok": failed == 0,
        "pins_checked": len(pins),
        "snapshots_saved": len(successful),
        "period": {"start": start.isoformat(), "end": today.isoformat()},
        "aggregate_metrics": {
            "impressions": total_impressions,
            "saves": total_saves,
            "outbound_clicks": total_outbound,
            "save_rate": round(total_saves / total_impressions, 4) if total_impressions else None,
            "outbound_click_rate": round(total_outbound / total_impressions, 4) if total_impressions else None,
        },
        "pin_results": results,
        "learning_status": "analytics_ingested_descriptive_evaluation_only" if successful else "analytics_unavailable",
        "model_trained": False,
        "note": "Uses live Pinterest API responses only. Predictive ML remains deferred until sufficient longitudinal data is available.",
    }
```

## Evidence tags

- `VERIFIED — SOURCE RETRIEVED`: Yes, from current main branch.
- `UNVERIFIED — LOGIC`: Full call-graph and tests not yet checked.
- `UNVERIFIED — LIVE BEHAVIOR`: No live side effects invoked.
