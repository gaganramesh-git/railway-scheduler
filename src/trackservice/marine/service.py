"""Live chartering server — serves the single dashboard, and lets an operator raise
a new cargo requirement or cancel a shipment and watch the plan re-optimise. Mirrors
the railway service: same roles, same audit, one dashboard, one entry screen.

The solve is sub-second, so every request re-plans from scratch — no caching needed.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import audit as _audit
from . import data as _data
from . import pipeline as _pipeline
from . import requests_store as _store
from .dashboard import build_html

app = FastAPI(title="Charter Planner", docs_url="/docs")
_M = {"seed": 3, "weeks": 12}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return build_html(_pipeline.run(**_M), live=True)


@app.get("/api/base")
def base() -> dict:
    return _pipeline.run(**_M)


@app.get("/api/entry/options")
def entry_options() -> dict:
    sc = _data.build_scenario(**_M)
    return {
        "ports": [{"id": p.id, "name": p.name, "max_draft_m": p.max_draft_m} for p in sc.ports],
        "origins": [{"id": o.id, "name": o.name, "transit_weeks": o.transit_weeks} for o in sc.origins],
        "vessels": [{"id": v.id, "name": v.name, "dwt": v.dwt, "draft_m": v.draft_m} for v in sc.vessels],
        "weeks": sc.weeks,
    }


class CargoRequest(BaseModel):
    origin: str = "AUS"
    port: str = "PPT"
    commodity: str = "Coking coal"
    volume_t: int = 55000
    required_by_week: int = 8
    priority: int = 5
    actor: str = "chartering-officer"


def _best_option(sc, req: CargoRequest):
    """Cheapest feasible (vessel, week) for a proposed cargo, or a reason it can't ship."""
    port = sc.port(req.port)
    origin = sc.origin(req.origin)
    fits = [v for v in sc.vessels if v.draft_m <= port.max_draft_m
            and v.loa_m <= port.max_loa_m and v.dwt >= req.volume_t]
    if not fits:
        deepest = max(sc.vessels, key=lambda v: v.dwt if v.draft_m <= port.max_draft_m else 0)
        return None, (f"No vessel fits {port.name}: its {port.max_draft_m} m draft caps at "
                      f"{deepest.name} ({deepest.dwt:,} t) but the parcel is {req.volume_t:,} t.")
    latest = req.required_by_week - origin.transit_weeks
    if latest < 0:
        return None, (f"Deadline too tight: {origin.name} is {origin.transit_weeks} weeks away, "
                      f"but the cargo is needed by week {req.required_by_week}.")
    best = None
    for v in fits:
        for w in range(0, min(latest, sc.weeks - 1) + 1):
            cost = v.base_rate_per_t * v.dwt * sc.rate(v.id, w)
            if best is None or cost < best["cost"]:
                best = {"vessel": v.id, "vessel_name": v.name, "week": w,
                        "arrive_week": w + origin.transit_weeks, "cost": round(cost, 0)}
    return best, None


@app.post("/api/charter/check")
def charter_check(req: CargoRequest) -> dict:
    sc = _data.build_scenario(**_M)
    best, reason = _best_option(sc, req)
    if best is None:
        return {"ok": False, "reason": reason}
    return {"ok": True, **best}


@app.post("/api/charter/commit")
def charter_commit(req: CargoRequest) -> dict:
    sc = _data.build_scenario(**_M)
    best, reason = _best_option(sc, req)
    if best is None:
        return {"ok": False, "reason": reason}
    rec = _store.record_addition({
        "commodity": req.commodity, "origin": req.origin, "port": req.port,
        "volume_t": req.volume_t, "required_by_week": req.required_by_week,
        "priority": req.priority, "actor": req.actor})
    _audit.record(req.actor, "cargo requirement raised",
                  f"{rec['id']}: {req.volume_t:,}t {req.commodity} {req.origin}->{req.port} by wk"
                  f"{req.required_by_week} — best {best['vessel_name']} wk{best['week']}")
    return {"ok": True, "id": rec["id"], "vessel": best["vessel_name"], "week": best["week"]}


class CancelRequest(BaseModel):
    parcel_id: str
    reason: str = "shipment cancelled"
    actor: str = "gm-commercial"


@app.post("/api/charter/cancel")
def charter_cancel(req: CancelRequest) -> dict:
    _store.record_cancellation(req.parcel_id, req.actor, req.reason)
    rep = _pipeline.run(**_M)
    _audit.record(req.actor, "shipment cancelled",
                  f"{req.parcel_id} cancelled ({req.reason}) — re-planned to "
                  f"${rep['metrics']['ours_cost']:,.0f}, {rep['metrics']['ours_voyages']} charters")
    return {"ok": True, "parcel_id": req.parcel_id,
            "new_cost": rep["metrics"]["ours_cost"], "new_voyages": rep["metrics"]["ours_voyages"]}


@app.get("/entry", response_class=HTMLResponse)
def entry_view() -> str:
    from .entry import entry_page
    return entry_page()


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    _pipeline.run(**_M)  # warm
    uvicorn.run(app, host=host, port=port, log_level="warning")
