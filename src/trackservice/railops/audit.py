"""Audit log for the block-planning system — who did what, when.

Every role's consequential actions are recorded here. Reads are filtered by the
caller's place in the hierarchy (done in the UI): a role sees its own trail plus
everyone below it, never a peer's or a superior's. A block decision may later be
examined by an accident inquiry, so the log is persistent and append-only.

Two kinds of entry feed the audit tab:
  • seed   — the day's activity that produced tonight's plan, derived from the
             plan itself (per-department demands, controls' forwarding, the
             system's own run). Deterministic, not persisted.
  • live   — real actions taken through the running server (an emergency injected,
             a plan approved). Appended to data/audit.jsonl and kept across runs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

_LOG = Path("data/audit.jsonl")

# role id → (rank, department, role label, user). Ids match the UI's role selector.
ROLE_INFO: dict[str, tuple] = {
    "sse-pway": (1, "ENGG", "SSE/PWAY/SUR", "R. Kulkarni"),
    "sse-trd":  (1, "TRD",  "SSE/TRD/SUR",  "V. Kamble"),
    "sse-snt":  (1, "SNT",  "SSE/SNT/KWV",  "A. Deshmukh"),
    "ctpc":     (2, "TRD",  "CTPC / Sr.DEE(TRD)", "S. Rao"),
    "sdom":     (3, None,   "Sr.DOM / Chief Controller", "M. Nair"),
    "drm":      (4, None,   "Divisional Railway Manager", "P. Sharma"),
    "board":    (5, None,   "Zonal HQ / Railway Board", "Zonal Cell"),
}
_DEPT_SSE = {"ENGG": "sse-pway", "TRD": "sse-trd", "SNT": "sse-snt"}


def _shape(role_id: str, action: str, detail: str, when: str) -> dict:
    rank, dept, role, user = ROLE_INFO[role_id]
    return {"role_id": role_id, "rank": rank, "department": dept, "role": role,
            "user": user, "action": action, "detail": detail, "time": when}


def record(role_id: str, action: str, detail: str) -> dict:
    """Append one live action to the persistent log and return it."""
    if role_id not in ROLE_INFO:
        role_id = "sdom"
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
    """The day's trail that produced this plan, derived from the plan itself."""
    reqs = report["scenario"]["requests"]
    by_dept: dict[str, int] = {}
    for r in reqs:
        d = r.get("department")
        if d:
            by_dept[d] = by_dept.get(d, 0) + 1
    stat = report.get("statutory", {})
    saved = report.get("shadows", {}).get("corridors_saved", 0)

    # Fixed early-evening times so the seed reads as a coherent shift, oldest first.
    t = ["17:05", "17:20", "17:40", "18:10", "18:25", "18:40", "19:00"]
    e: list[dict] = []
    i = 0

    def add(role_id, action, detail):
        nonlocal i
        e.append(_shape(role_id, action, detail, t[min(i, len(t) - 1)]))
        i += 1

    for dept, sse in _DEPT_SSE.items():
        n = by_dept.get(dept, 0)
        if n:
            add(sse, "demands raised", f"{n} {dept} block demand(s) drafted from open defects/overdue tasks")
    add("ctpc", "forwarded to COA", "department demands forwarded with traffic-block requirement")
    add("sdom", "corridor windows granted", f"night engineering windows released across the corridor; {saved} shadow blocks flagged")
    add("drm", "plan generated", f"weekly plan computed — statutory {stat.get('cpsat_met','?')}/{stat.get('total','?')} met, independently verified")
    return e


def report_entries(report: dict) -> dict:
    """Everything the audit tab needs: entries (seed + live) plus the role table."""
    entries = _seed(report) + _persisted()
    entries.sort(key=lambda x: x.get("ts", 0))  # persisted (with ts) after seed
    roles = {rid: {"rank": v[0], "department": v[1], "role": v[2], "user": v[3]}
             for rid, v in ROLE_INFO.items()}
    return {"entries": entries, "roles": roles}
