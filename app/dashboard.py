"""Read-only, authenticated live operations dashboard."""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.database import connection

router = APIRouter(tags=["dashboard"])
_COOKIE = "agent_dashboard_session"
_SESSION_TTL_SECONDS = 12 * 60 * 60


class DashboardLoginInput(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)


def _session_signature(timestamp: str) -> str:
    key = (settings.app_api_key or "").encode("utf-8")
    message = f"agent-dashboard-session:{timestamp}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _valid_session(request: Request) -> bool:
    if not settings.app_api_key:
        return False
    value = request.cookies.get(_COOKIE, "")
    try:
        timestamp, signature = value.split(".", 1)
        issued_at = int(timestamp)
    except (ValueError, TypeError):
        return False
    now = int(time.time())
    if issued_at > now or now - issued_at > _SESSION_TTL_SECONDS:
        return False
    return hmac.compare_digest(signature, _session_signature(timestamp))


def _require_session(request: Request) -> None:
    if not _valid_session(request):
        raise HTTPException(status_code=401, detail="Dashboard session expired. Please sign in again.")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML, headers={"Cache-Control": "no-store"})


@router.post("/dashboard/session")
def create_dashboard_session(payload: DashboardLoginInput) -> JSONResponse:
    expected = settings.app_api_key
    if not expected:
        raise HTTPException(status_code=503, detail="Dashboard authentication is not configured.")
    if not hmac.compare_digest(payload.api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid dashboard key.")
    issued = str(int(time.time()))
    response = JSONResponse({"authenticated": True})
    response.set_cookie(
        _COOKIE,
        f"{issued}.{_session_signature(issued)}",
        max_age=_SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/dashboard",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.delete("/dashboard/session")
def delete_dashboard_session() -> JSONResponse:
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(_COOKIE, path="/dashboard", secure=True, httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/dashboard/api/overview")
def dashboard_overview(request: Request) -> JSONResponse:
    _require_session(request)
    try:
        with connection() as conn:
            schedule = conn.execute(
                """
                SELECT id, account_id, timezone, starts_on, ends_on, daily_pin_limit,
                       board_name, status, created_at, updated_at
                FROM affiliate_publishing_schedules
                ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if not schedule:
                return JSONResponse({
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "schedule": None, "job_counts": {}, "upcoming_jobs": [],
                    "recent_jobs": [], "publication_counts": {}, "product_count": 0,
                }, headers={"Cache-Control": "no-store"})

            schedule_id = schedule["id"]
            counts = conn.execute(
                """SELECT status, count(*) AS total FROM affiliate_pin_jobs
                   WHERE schedule_id = %s GROUP BY status""",
                (schedule_id,),
            ).fetchall()
            upcoming = conn.execute(
                """
                SELECT j.id, p.product_name, j.run_at, j.local_run_date, j.daily_slot,
                       j.status, j.attempt_count
                FROM affiliate_pin_jobs j
                JOIN affiliate_product_sources p ON p.id = j.source_id
                WHERE j.schedule_id = %s AND j.status IN ('queued', 'processing')
                ORDER BY j.run_at, j.id LIMIT 8
                """,
                (schedule_id,),
            ).fetchall()
            recent = conn.execute(
                """
                SELECT j.id, p.product_name, j.run_at, j.finished_at, j.status,
                       j.attempt_count, j.safe_error_code, j.pinterest_pin_id
                FROM affiliate_pin_jobs j
                JOIN affiliate_product_sources p ON p.id = j.source_id
                WHERE j.schedule_id = %s
                ORDER BY COALESCE(j.finished_at, j.locked_at, j.run_at) DESC, j.id DESC
                LIMIT 10
                """,
                (schedule_id,),
            ).fetchall()
            publication_counts = conn.execute(
                """
                SELECT pp.status, count(*) AS total
                FROM pin_publications pp
                JOIN products p ON p.id = pp.product_id
                JOIN affiliate_pin_jobs j ON j.product_id = p.id
                WHERE j.schedule_id = %s
                GROUP BY pp.status
                """,
                (schedule_id,),
            ).fetchall()
            product_count = conn.execute(
                "SELECT count(*) AS total FROM affiliate_product_sources WHERE schedule_id = %s",
                (schedule_id,),
            ).fetchone()["total"]

        def iso(value):
            return value.isoformat() if value is not None else None

        return JSONResponse({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schedule": {
                "id": schedule["id"], "account_id": schedule["account_id"],
                "timezone": schedule["timezone"], "starts_on": schedule["starts_on"].isoformat(),
                "ends_on": schedule["ends_on"].isoformat(), "daily_pin_limit": schedule["daily_pin_limit"],
                "board_name": schedule["board_name"], "status": schedule["status"],
                "created_at": iso(schedule["created_at"]), "updated_at": iso(schedule["updated_at"]),
            },
            "job_counts": {row["status"]: row["total"] for row in counts},
            "upcoming_jobs": [{
                "id": row["id"], "product_name": row["product_name"], "run_at": iso(row["run_at"]),
                "local_run_date": row["local_run_date"].isoformat(), "daily_slot": row["daily_slot"],
                "status": row["status"], "attempt_count": row["attempt_count"],
            } for row in upcoming],
            "recent_jobs": [{
                "id": row["id"], "product_name": row["product_name"], "run_at": iso(row["run_at"]),
                "finished_at": iso(row["finished_at"]), "status": row["status"],
                "attempt_count": row["attempt_count"], "safe_error_code": row["safe_error_code"],
                "pinterest_pin_id": row["pinterest_pin_id"],
            } for row in recent],
            "publication_counts": {row["status"]: row["total"] for row in publication_counts},
            "product_count": product_count,
        }, headers={"Cache-Control": "no-store"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Dashboard data is temporarily unavailable.") from None


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#101827"><title>Affiliate Agent · Live Dashboard</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#121d2e;--line:#26364b;--muted:#9aabc0;--text:#edf4fc;--accent:#8bdbb0;--blue:#8abaff;--warn:#f2c879;--bad:#ff9292}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% -20%,#203957 0,transparent 48%),var(--bg);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:auto;padding:28px 20px 60px}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px}
.brand{display:flex;align-items:center;gap:12px}.mark{width:42px;height:42px;border-radius:13px;background:#193c38;color:var(--accent);display:grid;place-items:center;font-weight:900;font-size:20px}
h1{font-size:22px;line-height:1.2;margin:0}.sub,.muted{color:var(--muted);font-size:13px}.top-actions{display:flex;gap:9px;align-items:center}
button{border:1px solid var(--line);background:#1a2a40;color:var(--text);padding:10px 14px;border-radius:10px;font-weight:650;cursor:pointer}button.primary{background:var(--accent);color:#0b211a;border:0}
button:hover{filter:brightness(1.1)}.hidden{display:none!important}
.panel{background:linear-gradient(150deg,#152337,#101a29);border:1px solid var(--line);border-radius:16px;padding:18px;min-width:0}
.login{max-width:420px;margin:12vh auto}.login h2{margin:0 0 6px}.login input{width:100%;padding:13px;border:1px solid var(--line);border-radius:10px;background:#0b1422;color:var(--text);margin:16px 0 12px;font-size:16px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:16px 0}.metric .label{color:var(--muted);font-size:12px}.metric .value{font-size:29px;font-weight:760;letter-spacing:-.04em;margin-top:5px}.metric .hint{color:var(--muted);font-size:12px}
.section{display:flex;justify-content:space-between;align-items:center;margin:26px 0 12px}.section h2{font-size:16px;margin:0}.pill{display:inline-flex;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:750;background:#24334a;color:#cbd8e8;text-transform:uppercase;letter-spacing:.04em}.pill.active,.pill.succeeded{background:#173d32;color:#9ce4bf}.pill.queued,.pill.processing{background:#253a59;color:#a9ccff}.pill.failed,.pill.uncertain{background:#482b30;color:#ffb4b4}.pill.draft,.pill.paused{background:#4b3c25;color:#f4d28f}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}.schedule{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.kv{min-width:0}.kv span{display:block;color:var(--muted);font-size:12px}.kv strong{display:block;overflow-wrap:anywhere;margin-top:3px;font-size:14px}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:var(--muted);font-weight:600;padding:10px 8px;border-bottom:1px solid var(--line)}td{padding:11px 8px;border-bottom:1px solid #202e41;vertical-align:top}tr:last-child td{border:0}.table-wrap{overflow-x:auto}.empty{padding:22px 8px;color:var(--muted);text-align:center}
.error{color:var(--bad);font-size:13px;margin-top:10px}.foot{color:var(--muted);font-size:12px;margin-top:20px}
@media(max-width:760px){main{padding:20px 14px 45px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cols{grid-template-columns:1fr}.top{align-items:flex-start}.top-actions{flex-wrap:wrap;justify-content:flex-end}.metric .value{font-size:25px}}
@media(max-width:420px){.top{flex-direction:column}.top-actions{justify-content:flex-start}.schedule{grid-template-columns:1fr 1fr}}
</style></head><body><main>
<div id="login" class="panel login"><div class="brand"><div class="mark">P</div><div><h1>Affiliate Agent</h1><div class="sub">Secure operations dashboard</div></div></div><h2 style="margin-top:26px">Sign in</h2><p class="muted">Use your existing Agent API key. It is exchanged for a short-lived secure session and is not stored in this browser.</p><form id="loginForm"><input id="apiKey" type="password" autocomplete="current-password" placeholder="Agent API key" required><button class="primary" type="submit">Sign in securely</button><div id="loginError" class="error"></div></form></div>
<div id="app" class="hidden">
<header class="top"><div class="brand"><div class="mark">P</div><div><h1>Pinterest Affiliate Agent</h1><div class="sub">Live operations · read-only dashboard</div></div></div><div class="top-actions"><span class="muted" id="updated">Connecting…</span><button id="refresh">Refresh</button><button id="logout">Sign out</button></div></header>
<div class="grid">
<div class="panel metric"><div class="label">Queued jobs</div><div class="value" id="queued">—</div><div class="hint">Waiting for scheduled worker</div></div>
<div class="panel metric"><div class="label">Published successfully</div><div class="value" id="succeeded">—</div><div class="hint">Confirmed job outcomes</div></div>
<div class="panel metric"><div class="label">Failed / uncertain</div><div class="value" id="issues">—</div><div class="hint">Needs operator attention</div></div>
<div class="panel metric"><div class="label">Product sources</div><div class="value" id="products">—</div><div class="hint">Enabled/available schedule sources</div></div>
</div>
<div class="section"><h2>Active schedule</h2><span id="scheduleStatus" class="pill">—</span></div>
<div class="panel"><div class="schedule">
<div class="kv"><span>Schedule</span><strong id="scheduleId">—</strong></div><div class="kv"><span>Target board</span><strong id="board">—</strong></div>
<div class="kv"><span>Schedule window</span><strong id="window">—</strong></div><div class="kv"><span>Timezone / daily limit</span><strong id="zone">—</strong></div>
<div class="kv"><span>Pinterest account</span><strong id="account">—</strong></div><div class="kv"><span>Publication records</span><strong id="pubs">—</strong></div>
</div></div>
<div class="cols"><section><div class="section"><h2>Upcoming queue</h2><span class="muted">Next 8 jobs</span></div><div class="panel table-wrap"><table><thead><tr><th>Product</th><th>Scheduled</th><th>Status</th></tr></thead><tbody id="upcoming"></tbody></table></div></section>
<section><div class="section"><h2>Recent activity</h2><span class="muted">Latest 10 jobs</span></div><div class="panel table-wrap"><table><thead><tr><th>Product</th><th>Finished / scheduled</th><th>Status</th></tr></thead><tbody id="recent"></tbody></table></div></section></div>
<div class="foot">Auto-refreshes every 30 seconds. This dashboard is read-only: it cannot publish Pins, create Boards, activate schedules, or change products. Affiliate URLs, OAuth tokens, and API keys are never displayed.</div>
<div id="dataError" class="error"></div></div></main>
<script>
const $=id=>document.getElementById(id);let timer=null;
function esc(v){return String(v??"—").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function when(v,zone){if(!v)return "—";try{return new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short",timeZone:zone||"UTC"}).format(new Date(v));}catch{return v;}}
function pill(s){return '<span class="pill '+esc(s)+'">'+esc(s)+'</span>';}
function rows(target,items,zone,recent){const body=$(target);body.innerHTML="";if(!items.length){body.innerHTML='<tr><td colspan="3" class="empty">No jobs to display</td></tr>';return;}
for(const x of items){const tr=document.createElement("tr");const timeValue=recent?(x.finished_at||x.run_at):x.run_at;tr.innerHTML='<td>'+esc(x.product_name)+'</td><td>'+esc(when(timeValue,zone))+'</td><td>'+pill(x.status)+'</td>';body.appendChild(tr);}}
async function load(){try{const r=await fetch("/dashboard/api/overview",{credentials:"same-origin",cache:"no-store"});if(r.status===401){showLogin();return;}if(!r.ok)throw new Error("Dashboard data request failed ("+r.status+").");const d=await r.json();const s=d.schedule;const counts=d.job_counts||{};$("queued").textContent=counts.queued||0;$("succeeded").textContent=counts.succeeded||0;$("issues").textContent=(counts.failed||0)+(counts.uncertain||0);$("products").textContent=d.product_count??0;
$("scheduleStatus").className="pill "+(s?.status||"");$("scheduleStatus").textContent=s?.status||"No schedule";$("scheduleId").textContent=s?"#"+s.id:"—";$("board").textContent=s?.board_name||"—";$("window").textContent=s?s.starts_on+" → "+s.ends_on:"—";$("zone").textContent=s?s.timezone+" · "+s.daily_pin_limit+"/day":"—";$("account").textContent=s?.account_id||"—";
const pc=d.publication_counts||{};$("pubs").textContent=Object.entries(pc).map(([k,v])=>k+": "+v).join(" · ")||"No publication records";rows("upcoming",d.upcoming_jobs||[],s?.timezone,false);rows("recent",d.recent_jobs||[],s?.timezone,true);$("updated").textContent="Updated "+when(d.generated_at,"UTC");$("dataError").textContent="";
}catch(e){$("dataError").textContent=e.message;}}
function showApp(){ $("login").classList.add("hidden");$("app").classList.remove("hidden");load();if(timer)clearInterval(timer);timer=setInterval(load,30000);}
function showLogin(){if(timer)clearInterval(timer);$("app").classList.add("hidden");$("login").classList.remove("hidden");}
$("loginForm").addEventListener("submit",async e=>{e.preventDefault();$("loginError").textContent="";try{const r=await fetch("/dashboard/session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({api_key:$("apiKey").value})});$("apiKey").value="";if(!r.ok)throw new Error("Sign-in failed. Check the key and try again.");showApp();}catch(err){$("loginError").textContent=err.message;}});
$("refresh").addEventListener("click",load);$("logout").addEventListener("click",async()=>{await fetch("/dashboard/session",{method:"DELETE"});showLogin();});
fetch("/dashboard/api/overview",{credentials:"same-origin"}).then(r=>{if(r.ok)showApp();else showLogin();}).catch(showLogin);
</script></body></html>"""
