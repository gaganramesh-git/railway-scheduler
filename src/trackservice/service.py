"""Live solve server — lets the dashboard ring the solver on demand.

The static dashboard bakes its answers in. This server serves the same dashboard
in LIVE mode, where a judge can invent an emergency and watch the real solver
place it. It's the exact `pipeline.run()` the CLI uses — the server is just the
doorbell.

Runs entirely on localhost, no internet. Start it with `trackservice serve`.
"""

from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import data as _data
from . import pipeline as _pipeline
from .dashboard import build_html
from .types import CrewType, Equipment, Priority, Request, hours_to_ticks

app = FastAPI(title="Track Service", docs_url="/docs")

# Base run parameters — fixed so the baseline plan is stable between solves.
_BASE = {"seed": 7, "n_requests": 40, "nights": 5}
_SIH = {"seed": 1, "nights": 30}
_MODE = "synthetic"  # or "sih" — set by serve()/serve_sih()


def _sih():
    from .railops import sih_pipeline
    return sih_pipeline


# The SIH plan is cached and only recomputed when the committed-demands file
# changes. The plan itself is cheap; the per-job EXPLANATIONS/ALTERNATIVES are
# not, so they're split into a second cache the dashboard fetches lazily — every
# page load and action stays snappy, and the analysis panels fill in a moment
# later instead of blocking the whole month-long plan.
_SIH_CACHE: dict = {"key": None, "report": None}
_SIH_ANALYSIS: dict = {"key": None, "data": None}


def _demands_key():
    import os
    try:
        return os.path.getmtime("data/demands.jsonl")
    except OSError:
        return 0


def _sih_base() -> dict:
    """The plan without the expensive analysis — fast (~1s), served immediately."""
    key = _demands_key()
    if _SIH_CACHE["key"] != key or _SIH_CACHE["report"] is None:
        _SIH_CACHE["report"] = _sih().run(**_SIH, analyze=False)
        _SIH_CACHE["key"] = key
    return _SIH_CACHE["report"]


def _sih_analysis() -> dict:
    """The explanations + alternatives, computed once and cached (the slow part)."""
    key = _demands_key()
    if _SIH_ANALYSIS["key"] != key or _SIH_ANALYSIS["data"] is None:
        full = _sih().run(**_SIH, analyze=True)
        _SIH_ANALYSIS["data"] = {
            "explanations": full["explanations"],
            "alternatives": full["alternatives"],
        }
        _SIH_ANALYSIS["key"] = key
    return _SIH_ANALYSIS["data"]


def _sih_invalidate() -> None:
    _SIH_CACHE["key"] = None
    _SIH_CACHE["report"] = None
    _SIH_ANALYSIS["key"] = None
    _SIH_ANALYSIS["data"] = None


class CustomEmergency(BaseModel):
    """A judge-authored emergency. Everything has a sane default so a bare
    request still solves."""

    section: str = "SEC-H"
    night: int = 0            # 0-indexed
    duration_h: float = 2.5
    crew: str = "p-way"
    crew_size: int = 2
    equipment: str = "road-railer"
    priority: int = 5
    title: str = "EMERGENCY (live)"
    actor: str = "sdom"       # who performed this action (role id)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the dashboard in LIVE mode with a fresh base run embedded."""
    if _MODE == "sih":
        return build_html(_sih_base(), live=True)
    return build_html(_pipeline.run(**_BASE), live=True)


@app.get("/api/base")
def base() -> dict:
    """The default report — same as the static dashboard, as JSON."""
    return _sih_base() if _MODE == "sih" else _pipeline.run(**_BASE)


@app.get("/api/analysis")
def analysis() -> dict:
    """The lazy analysis panels (explanations + alternatives) for the base plan."""
    if _MODE != "sih":
        return {"explanations": [], "alternatives": []}
    return _sih_analysis()


@app.post("/api/solve")
def solve(emg: CustomEmergency) -> dict:
    """Re-solve with a judge-authored emergency forced in, and return the report."""
    if _MODE == "sih":
        from .railops import audit as _audit
        from .railops import generator as _gen
        scenario, _ = _gen.build_scenario(**_SIH)
        custom = _to_request(scenario, emg)
        rep = _sih().run(**_SIH, custom_emergency=custom, analyze=False)
        e = rep["emergency"]
        _audit.record(emg.actor, "emergency injected",
                      f"{emg.title} on {emg.section} night {emg.night+1}; "
                      f"bumped {', '.join(e['bumped']) or 'nothing'}; statutory {rep['statutory']['cpsat_met']}/{rep['statutory']['total']} held")
        rep["audit"] = _audit.report_entries(rep)  # include the entry just recorded
        return rep
    scenario = _data.build_scenario(**_BASE)
    custom = _to_request(scenario, emg)
    return _pipeline.run(**_BASE, custom_emergency=custom)


class ApplyRequest(BaseModel):
    ids: list[str]   # cumulative set of pinned jobs
    actor: str = "drm"


@app.post("/api/apply")
def apply(req: ApplyRequest) -> dict:
    """Commit the pinned alternatives — force them all in and re-solve one plan."""
    if _MODE == "sih":
        from .railops import audit as _audit
        rep = _sih().run(**_SIH, apply_ids=req.ids, analyze=False)
        _audit.record(req.actor, "alternative applied", f"pinned {', '.join(req.ids)}")
        rep["audit"] = _audit.report_entries(rep)
        return rep
    return _pipeline.run_apply(**_BASE, apply_ids=req.ids)




def _to_request(scenario, emg: CustomEmergency) -> Request:
    """Turn the form payload into a domain Request, snapping bad input to safe values."""
    section_ids = {s.id for s in scenario.sections}
    section = emg.section if emg.section in section_ids else scenario.sections[0].id
    night = max(0, min(emg.night, scenario.nights - 1))

    try:
        crew = CrewType(emg.crew)
    except ValueError:
        crew = CrewType.PWAY
    try:
        equipment = Equipment(emg.equipment)
    except ValueError:
        equipment = Equipment.NONE
    try:
        priority = Priority(emg.priority)
    except ValueError:
        priority = Priority.URGENT

    n = sum(1 for r in scenario.requests if r.is_emergency) + 1
    return Request(
        id=f"EMG-{n:03d}",
        title=emg.title or "EMERGENCY (live)",
        section_id=section,
        duration=hours_to_ticks(round(emg.duration_h * 2) / 2),  # snap to half-hour
        priority=priority,
        crew=crew,
        crew_size=max(1, emg.crew_size),
        equipment=equipment,
        earliest_night=night,
        latest_night=night,
        is_emergency=True,
    )


@app.get("/depot", response_class=HTMLResponse)
def depot_view() -> str:
    """The Depot Incharge entry screen (SIH mode only in practice)."""
    from .railops.depot import depot_page
    return depot_page()


@app.get("/api/depot/sections")
def depot_sections() -> dict:
    from .railops import generator as _gen
    scenario, _ = _gen.build_scenario(**_SIH)
    return {
        "sections": [{"id": s.id, "name": s.name, "traffic": s.traffic_density}
                     for s in scenario.sections],
        "nights": scenario.nights,
    }


class DepotDemand(BaseModel):
    department: str = "ENGG"
    crew: str = "p-way"
    section: str = "SEC-A"
    reason_code: str = "ETMW"
    duration_h: float = 2.5
    equipment: str = "none"
    night: int = 3   # 1-based "needed by" night
    actor: str = "sse-pway"


@app.post("/api/depot/check")
def depot_check(d: DepotDemand) -> dict:
    """Add the depot's proposed demand, re-solve, and answer in plain English."""
    from dataclasses import replace as _replace

    from .explain import explain_unscheduled
    from .railops import generator as _gen
    from .railops import sih_pipeline as _sp
    from .types import format_clock

    scenario, meta = _gen.build_scenario(**_SIH)
    t0 = {rid for rid, m in meta.items() if m.tier == 0}

    # Pin the check to the EXACT night the engineer asked for — the same night the
    # commit will pin it to — so "fits night N" matches where the block lands.
    night0 = max(0, min(d.night - 1, scenario.nights - 1))
    new = _to_request(scenario, CustomEmergency(
        section=d.section, night=night0, duration_h=d.duration_h,
        crew=d.crew, crew_size=1, equipment=d.equipment, priority=4, title=d.reason_code,
    ))
    new = _replace(new, id="NEW", is_emergency=False, earliest_night=night0, latest_night=night0)
    sc2 = scenario.with_request(new)

    from .railops import audit as _audit

    plan = _solver_solve(sc2, t0)
    a = plan.assignment("NEW")
    if a is not None:
        _audit.record(d.actor, "demand raised",
                      f"{d.reason_code} {d.duration_h}h on {d.section} — fits night {a.night+1} "
                      f"{format_clock(a.start)}–{format_clock(a.end)}")
        return {"ok": True, "night": a.night + 1,
                "start": format_clock(a.start), "end": format_clock(a.end)}

    # Not in the optimal plan — can it fit by displacing lower work?
    forced = _solver_solve(sc2, t0 | {"NEW"})
    fa = forced.assignment("NEW")
    if fa is not None:
        bumped = sorted(plan.scheduled_ids - forced.scheduled_ids)
        return {"ok": False, "fits_by_bumping": True, "night": fa.night + 1, "bumped": bumped}

    # Genuinely can't fit — say why, in the field engineer's language.
    exp = explain_unscheduled(sc2, ["NEW"])
    reason = exp[0].detail if exp else "No feasible slot on this section within the nights allowed."
    suggestion = _suggestion(exp[0] if exp else None)
    return {"ok": False, "reason": reason, "suggestion": suggestion}


@app.post("/api/depot/commit")
def depot_commit(d: DepotDemand) -> dict:
    """Commit a checked demand into the plan — it persists and shows on the graph."""
    from .railops import audit as _audit
    from .railops import demands as _demands

    rec = _demands.record({
        "department": d.department, "crew": d.crew, "section": d.section,
        "reason_code": d.reason_code, "duration_h": d.duration_h,
        "equipment": d.equipment, "night": d.night, "actor": d.actor,
    })
    _audit.record(d.actor, "demand committed",
                  f"{rec['id']}: {d.reason_code} {d.duration_h}h on {d.section} "
                  f"night {d.night} — pinned into the plan")
    # Recompute the plan now (the demands file changed, so this refreshes the cache)
    # so the dashboard the engineer is redirected to loads instantly, already showing
    # the block — instead of triggering a slow re-solve on arrival.
    report = _sih_base()
    placed = next((a for a in report["optimal"]["assignments"] if a["id"] == rec["id"]), None)
    night = (placed["night"] + 1) if placed else d.night
    return {"ok": True, "id": rec["id"], "night": night, "scheduled": placed is not None}


def _solver_solve(scenario, mandatory):
    from . import solver as _solver
    return _solver.solve(scenario, time_limit=4.0, mandatory=mandatory)


def _suggestion(exp) -> str:
    if exp is None:
        return "widen the 'needed by' night, or split into two shorter blocks."
    if "window" in exp.binding:
        return "no block is long enough — split the work into two shorter blocks."
    if "crew" in exp.binding:
        return "the crew is booked — try a different night."
    if "equipment" in exp.binding:
        return "the machine is committed elsewhere — try another night."
    return "widen the 'needed by' night to give the planner room."


def serve(host: str = "127.0.0.1", port: int = 8000, sih: bool = False) -> None:
    global _MODE
    _MODE = "sih" if sih else "synthetic"
    if sih:
        # Warm the plan cache before serving so the first page load is instant.
        _sih_base()
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")
