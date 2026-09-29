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


def cancelled_ids() -> set[str]:
    return {r["parcel_id"] for r in _read(_CANCEL)}


def additions() -> list[dict]:
    return _read(_ADD)


def apply_to(scenario: Scenario):
    """Fold operator edits into the scenario. Returns (scenario, manual_ids, cancelled).

    Manually-raised cargo becomes a pinned high-priority parcel; cancelled parcels
    (base or manual) are dropped so the re-solve frees their capacity."""
    cancelled = cancelled_ids()
    manual: list[CargoParcel] = []
    for d in _read(_ADD):
        if d["id"] in cancelled:
            continue
        manual.append(CargoParcel(
            id=d["id"], commodity=d.get("commodity", "Coal"),
            origin_id=d["origin"], port_id=d["port"], volume_t=int(d["volume_t"]),
            required_by_week=int(d["required_by_week"]),
            priority=int(d.get("priority", 5)), manual=True))
    kept = [p for p in scenario.parcels if p.id not in cancelled]
    scenario2 = replace(scenario, parcels=kept + manual)
    return scenario2, [m.id for m in manual], sorted(cancelled)
