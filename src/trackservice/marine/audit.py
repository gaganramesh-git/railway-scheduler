"""Controlled access + audit trail for the chartering system.

Mirrors the railway module: every action is recorded with the role that took it,
and a person sees the audit of their own level and everyone below them in the
hierarchy. Roles reflect a steel-plant / procurement chartering chain.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_LOG = Path("data/charter_audit.jsonl")

# role_id -> (rank, department, role title, user)
ROLE_INFO: dict[str, tuple] = {
    "chartering-officer": (1, "CHARTER", "Chartering Officer", "R. Menon"),
    "procurement-mgr":    (2, "PROC",    "Procurement Manager", "S. Iyer"),
    "logistics-head":     (3, None,      "Logistics Head (DGM Materials)", "A. Banerjee"),
    "gm-commercial":      (4, None,      "GM (Commercial)", "P. Rao"),
    "board":              (5, None,      "Director (Finance) / Board", "Steel HQ"),
}


def _shape(role_id: str, action: str, detail: str, when: str) -> dict:
    rank, dept, role, user = ROLE_INFO[role_id]
    return {"role_id": role_id, "rank": rank, "department": dept, "role": role,
            "user": user, "action": action, "detail": detail, "time": when}


def record(role_id: str, action: str, detail: str) -> dict:
    if role_id not in ROLE_INFO:
        role_id = "logistics-head"
    entry = _shape(role_id, action, detail, time.strftime("%d %b %H:%M"))
    entry["ts"] = time.time()
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    with _LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


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


def _seed(report: dict) -> list[dict]:
    """The trail that produced this plan, derived from the plan itself, so the audit
    is populated before anyone acts live."""
    m = report["metrics"]
    n_manual = sum(1 for p in report["scenario"]["parcels"] if p.get("manual"))
    entries = [
        ("chartering-officer", "requirements filed",
         f"{m['total_parcels'] - n_manual} cargo requirements logged for the horizon"),
        ("procurement-mgr", "budget cleared",
         f"freight budget approved; benchmark spot cost ${m['spot_cost']:,.0f}"),
        ("logistics-head", "lanes & ports validated",
         "origin lanes and discharge-port draft limits confirmed"),
        ("gm-commercial", "charter plan approved",
         f"optimised plan signed off - ${m['ours_cost']:,.0f}, {m['cost_saved_pct']}% under spot, "
         f"{m['ours_voyages']} charters"),
    ]
    now = time.strftime("%d %b %H:%M")
    return [_shape(r, a, d, now) for r, a, d in entries]


def report_entries(report: dict) -> dict:
    entries = _seed(report) + _persisted()
    entries.sort(key=lambda e: e.get("ts", 0))
    return {
        "entries": entries,
        "roles": {rid: {"rank": v[0], "department": v[1], "role": v[2], "user": v[3]}
                  for rid, v in ROLE_INFO.items()},
    }
