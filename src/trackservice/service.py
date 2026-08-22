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


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the dashboard in LIVE mode with a fresh base run embedded."""
    report = _pipeline.run(**_BASE)
    return build_html(report, live=True)


@app.get("/api/base")
def base() -> dict:
    """The default report — same as the static dashboard, as JSON."""
    return _pipeline.run(**_BASE)


@app.post("/api/solve")
def solve(emg: CustomEmergency) -> dict:
    """Re-solve with a judge-authored emergency forced in, and return the report."""
    scenario = _data.build_scenario(**_BASE)
    custom = _to_request(scenario, emg)
    return _pipeline.run(**_BASE, custom_emergency=custom)


class ApplyRequest(BaseModel):
    ids: list[str]   # cumulative set of pinned jobs


@app.post("/api/apply")
def apply(req: ApplyRequest) -> dict:
    """Commit the pinned alternatives — force them all in and re-solve one plan."""
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


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")
