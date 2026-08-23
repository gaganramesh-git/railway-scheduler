"""Committed depot demands — the tasks a field engineer raised and committed.

The depot screen checks 'will it fit'; when the engineer commits, we persist the
demand here (data/demands.jsonl) so it becomes a real job in the plan. On every
subsequent solve these are folded into the scenario and pinned, so they show up
as blocks on the graph instead of being thrown away after the check.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..types import CrewType, Equipment, Priority, Request, hours_to_ticks
from .generator import JobMeta

_LOG = Path("data/demands.jsonl")

# Committed demands compete just below statutory/urgent work, but we pin them
# (mandatory) at solve time so a committed task always appears on the graph.
_TIER = 2


def record(demand: dict) -> dict:
    """Persist one committed demand and return the stored record (with an id)."""
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    n = len(_persisted()) + 1
    rec = dict(demand)
    rec["id"] = f"DMD-{n:03d}"
    rec["ts"] = time.time()
    rec["time"] = time.strftime("%d %b %H:%M")
    with _LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def _persisted() -> list[dict]:
    if not _LOG.exists():
        return []
    out = []
    for line in _LOG.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def committed() -> list[dict]:
    """All demands committed from the depot screen, oldest first."""
    return _persisted()


def apply_to(scenario, meta: dict, nights: int):
    """Fold every committed demand into the scenario as a pinned Request.

    Returns (scenario, meta, ids) — ids are the committed job ids to pin so they
    are guaranteed a slot on the graph. Demands whose section no longer exists or
    whose night is out of range are snapped to safe values.
    """
    section_ids = {s.id for s in scenario.sections}
    ids: list[str] = []
    for d in _persisted():
        rid = d["id"]
        section = d["section"] if d["section"] in section_ids else scenario.sections[0].id
        night = max(0, min(int(d.get("night", 1)) - 1, nights - 1))  # stored 1-based
        try:
            crew = CrewType(d.get("crew", "p-way"))
        except ValueError:
            crew = CrewType.PWAY
        try:
            equipment = Equipment(d.get("equipment", "none"))
        except ValueError:
            equipment = Equipment.NONE
        req = Request(
            id=rid,
            title=d.get("reason_code", "DEMAND"),
            section_id=section,
            duration=hours_to_ticks(round(float(d.get("duration_h", 2.5)) * 2) / 2),
            priority=Priority.URGENT,
            crew=crew,
            crew_size=1,
            equipment=equipment,
            earliest_night=night,
            latest_night=night,
        )
        scenario = scenario.with_request(req)
        meta[rid] = JobMeta(
            reason_code=d.get("reason_code", "DEMAND"),
            department=d.get("department", "ENGG"),
            tier=_TIER,
            committed=True,
        )
        ids.append(rid)
    return scenario, meta, ids
