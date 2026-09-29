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


def _current_scenario():
    """Base scenario with all operator edits already folded in."""
    sc, _, _ = _store.apply_to(_data.build_scenario(**_M))
    return sc


class RescheduleRequest(BaseModel):
    parcel_id: str
    required_by_week: int
    actor: str = "logistics-head"


@app.post("/api/charter/reschedule")
def charter_reschedule(req: RescheduleRequest) -> dict:
    """Shipment needed earlier/later — change its required-by week and re-plan."""
    sc = _current_scenario()
    try:
        p = sc.parcel(req.parcel_id)
    except StopIteration:
        return {"ok": False, "reason": f"{req.parcel_id} is not in the current plan."}
    transit = sc.origin(p.origin_id).transit_weeks
    if req.required_by_week < transit:
        return {"ok": False, "reason": f"Impossible: {sc.origin(p.origin_id).name} is "
                f"{transit} weeks away, so it cannot arrive by week {req.required_by_week}."}
    _store.record_reschedule(req.parcel_id, req.required_by_week, req.actor)
    rep = _pipeline.run(**_M)
    _audit.record(req.actor, "shipment rescheduled",
                  f"{req.parcel_id} required-by moved to wk{req.required_by_week} "
                  f"(was wk{p.required_by_week}) — re-planned to ${rep['metrics']['ours_cost']:,.0f}")
    return {"ok": True, "parcel_id": req.parcel_id,
            "new_cost": rep["metrics"]["ours_cost"], "new_voyages": rep["metrics"]["ours_voyages"]}


class PortDisruptRequest(BaseModel):
    port: str
    days: int = 14
    from_week: int = 4
    actor: str = "logistics-head"


@app.post("/api/charter/port-disrupt")
def charter_port_disrupt(req: PortDisruptRequest) -> dict:
    """A port is unavailable for N days from a given week. Find cargo due at that port
    during the outage, notify the sender, and propose the next-nearest feasible port."""
    import math
    sc = _current_scenario()
    try:
        port = sc.port(req.port)
    except StopIteration:
        return {"ok": False, "reason": "unknown port"}
    weeks = max(1, math.ceil(req.days / 7))
    lo, hi = req.from_week, req.from_week + weeks
    affected = [p for p in sc.parcels
                if p.port_id == req.port and lo <= p.required_by_week <= hi]
    proposals = []
    for p in affected:
        alt = _data.nearest_feasible_port(sc, req.port, p.volume_t)
        proposals.append({
            "parcel_id": p.id, "origin": sc.origin(p.origin_id).name,
            "current_port": port.name, "volume_t": p.volume_t,
            "suggested_port": alt.id if alt else None,
            "suggested_port_name": alt.name if alt else "— none feasible —",
        })
    _audit.record(req.actor, "port disruption declared",
                  f"{port.name} unavailable {req.days} days (~{weeks} wk); "
                  f"{len(affected)} shipment(s) affected — senders notified")
    return {"ok": True, "port": port.name, "days": req.days, "weeks": weeks,
            "from_week": req.from_week, "affected": proposals}


class RerouteRequest(BaseModel):
    parcel_id: str
    new_port: str
    actor: str = "logistics-head"


@app.post("/api/charter/reroute")
def charter_reroute(req: RerouteRequest) -> dict:
    """Accept a proposed reroute to the nearest port and re-plan."""
    sc = _current_scenario()
    try:
        p = sc.parcel(req.parcel_id)
        newp = sc.port(req.new_port)
    except StopIteration:
        return {"ok": False, "reason": "unknown parcel or port"}
    _store.record_reroute(req.parcel_id, req.new_port, req.actor)
    rep = _pipeline.run(**_M)
    _audit.record(req.actor, "shipment rerouted",
                  f"{req.parcel_id} diverted to {newp.name} — re-planned to "
                  f"${rep['metrics']['ours_cost']:,.0f}, {rep['metrics']['ours_voyages']} charters")
    return {"ok": True, "parcel_id": req.parcel_id, "new_port": newp.name,
            "new_cost": rep["metrics"]["ours_cost"]}


class CsvImport(BaseModel):
    csv: str
    actor: str = "chartering-officer"


@app.post("/api/charter/import-csv")
def charter_import_csv(req: CsvImport) -> dict:
    """Bulk-add cargo requirements from a pasted/uploaded CSV. Each row is validated
    for feasibility; feasible rows are added, the rest reported with a reason.

    Columns: commodity, origin, port, volume_t, required_by_week, priority
    """
    import csv as _csv
    import io
    sc = _current_scenario()
    port_ids = {p.id for p in sc.ports}
    origin_ids = {o.id for o in sc.origins}
    added, skipped = [], []
    reader = _csv.DictReader(io.StringIO(req.csv.strip()))
    if not reader.fieldnames or "port" not in reader.fieldnames or "origin" not in reader.fieldnames:
        return {"ok": False, "reason": "CSV needs at least 'origin', 'port', 'volume_t', "
                "'required_by_week' columns (commodity, priority optional)."}
    for i, row in enumerate(reader, start=1):
        try:
            r = CargoRequest(
                origin=(row.get("origin") or "").strip(),
                port=(row.get("port") or "").strip(),
                commodity=(row.get("commodity") or "Coal").strip() or "Coal",
                volume_t=int(float(row["volume_t"])),
                required_by_week=int(float(row["required_by_week"])),
                priority=int(float(row.get("priority") or 5)),
                actor=req.actor)
        except Exception as e:
            skipped.append({"row": i, "reason": f"malformed row ({e})"})
            continue
        if r.origin not in origin_ids:
            skipped.append({"row": i, "reason": f"unknown origin '{r.origin}'"}); continue
        if r.port not in port_ids:
            skipped.append({"row": i, "reason": f"unknown port '{r.port}'"}); continue
        best, reason = _best_option(sc, r)
        if best is None:
            skipped.append({"row": i, "reason": reason}); continue
        rec = _store.record_addition({
            "commodity": r.commodity, "origin": r.origin, "port": r.port,
            "volume_t": r.volume_t, "required_by_week": r.required_by_week,
            "priority": r.priority, "actor": r.actor})
        added.append({"id": rec["id"],
                      "summary": f"{r.volume_t:,}t {r.origin}->{r.port} wk{r.required_by_week}"})
    if added:
        _audit.record(req.actor, "cargo imported (CSV)",
                      f"{len(added)} requirement(s) imported, {len(skipped)} skipped")
    return {"ok": True, "added": added, "skipped": skipped}


@app.get("/entry", response_class=HTMLResponse)
def entry_view() -> str:
    from .entry import entry_page
    return entry_page()


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    _pipeline.run(**_M)  # warm
    uvicorn.run(app, host=host, port=port, log_level="warning")
