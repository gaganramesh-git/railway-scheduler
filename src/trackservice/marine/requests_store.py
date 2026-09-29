"""Persistence for operator edits to the cargo demand set — the marine counterpart
of the railway demands store. Two kinds of edit:

  * additions    — a requirement raised by hand through the charter-entry screen
  * cancellations — a shipment pulled; the plan is re-optimised without it

Both survive restarts (JSONL under data/) and both fold into the scenario before
the next solve, so a raised cargo appears on the schedule and a cancelled one
disappears and frees its capacity.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from .model import CargoParcel, Scenario

_ADD = Path("data/cargo_requests.jsonl")
_CANCEL = Path("data/cargo_cancellations.jsonl")
_RESCHED = Path("data/cargo_reschedules.jsonl")
_REROUTE = Path("data/cargo_reroutes.jsonl")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def record_addition(cargo: dict) -> dict:
    _ADD.parent.mkdir(parents=True, exist_ok=True)
    rec = dict(cargo)
    rec["id"] = f"CR-{len(_read(_ADD)) + 1:03d}"
    rec["ts"] = time.time()
    with _ADD.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def record_cancellation(parcel_id: str, actor: str, reason: str) -> dict:
    _CANCEL.parent.mkdir(parents=True, exist_ok=True)
    rec = {"parcel_id": parcel_id, "actor": actor, "reason": reason, "ts": time.time()}
    with _CANCEL.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def record_reschedule(parcel_id: str, required_by_week: int, actor: str) -> dict:
    _RESCHED.parent.mkdir(parents=True, exist_ok=True)
    rec = {"parcel_id": parcel_id, "required_by_week": int(required_by_week),
           "actor": actor, "ts": time.time()}
    with _RESCHED.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def record_reroute(parcel_id: str, new_port: str, actor: str) -> dict:
    _REROUTE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"parcel_id": parcel_id, "new_port": new_port, "actor": actor, "ts": time.time()}
    with _REROUTE.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def cancelled_ids() -> set[str]:
    return {r["parcel_id"] for r in _read(_CANCEL)}


def _latest(path: Path, field: str) -> dict:
    """Last value wins for repeated edits to the same parcel."""
    out = {}
    for r in _read(path):
        out[r["parcel_id"]] = r[field]
    return out


def additions() -> list[dict]:
    return _read(_ADD)


def apply_to(scenario: Scenario):
    """Fold operator edits into the scenario. Returns (scenario, manual_ids, cancelled).

    Manually-raised cargo becomes a pinned high-priority parcel; cancelled parcels
    (base or manual) are dropped so the re-solve frees their capacity."""
    cancelled = cancelled_ids()
    resched = _latest(_RESCHED, "required_by_week")   # parcel_id -> new week
    reroute = _latest(_REROUTE, "new_port")           # parcel_id -> new port
    manual: list[CargoParcel] = []
    for d in _read(_ADD):
        if d["id"] in cancelled:
            continue
        manual.append(CargoParcel(
            id=d["id"], commodity=d.get("commodity", "Coal"),
            origin_id=d["origin"], port_id=d["port"], volume_t=int(d["volume_t"]),
            required_by_week=int(d["required_by_week"]),
            priority=int(d.get("priority", 5)), manual=True))

    def edited(p: CargoParcel) -> CargoParcel:
        changes = {}
        if p.id in resched:
            changes["required_by_week"] = resched[p.id]
        if p.id in reroute:
            changes["port_id"] = reroute[p.id]
        return replace(p, **changes) if changes else p

    kept = [edited(p) for p in scenario.parcels if p.id not in cancelled]
    manual = [edited(m) for m in manual]
    scenario2 = replace(scenario, parcels=kept + manual)
    return scenario2, [m.id for m in manual], sorted(cancelled)
