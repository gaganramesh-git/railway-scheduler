"""Adapters for the upstream railway systems the block planner integrates with.

The problem statement names four sources:

  * TMS  — Track Management System        → Engineering (P-Way) defects
  * SMMS — Signalling Maintenance & Mgmt  → Signal & Telecom faults
  * TDMS — Traction Distribution Mgmt     → OHE / traction defects
  * COA  — Control Office Application      → block/corridor availability + goods forecast

Each system exports flat files (CSV). This module reads those export shapes into
the planner's internal demand model, and can also *write* realistic sample exports
from a scenario — so the whole pipeline can run from files instead of the in-memory
generator, demonstrating the integration end to end.

Dates in the feeds are absolute (that's how the real systems record them); we map
them to the planner's night index relative to PLAN_START.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from ..types import (
    CrewType, Equipment, Priority, Request, Scenario, Section, Window,
    format_clock, hours_to_ticks,
)
from . import generator as _gen
from .generator import JobMeta
from .timetable import load_corridor

FEEDS_DIR = "data/feeds"
PLAN_START = date(2026, 9, 1)   # night 0 of the planning horizon

# tier → the planner's priority. T0/T1 are both operationally urgent; T0 is the
# statutory, hard-deadline subset (IMR, USFD IMR, OHE breakdown).
_TIER_PRIORITY = {0: Priority.URGENT, 1: Priority.URGENT, 2: Priority.IMPORTANT, 3: Priority.ROUTINE}
_CREW = {"ENGG": CrewType.PWAY, "TRD": CrewType.OHE, "SNT": CrewType.SIGNAL}
_SYSTEM = {"ENGG": "TMS", "TRD": "TDMS", "SNT": "SMMS"}
_FILE = {"ENGG": "tms_defects.csv", "TRD": "tdms_defects.csv", "SNT": "smms_defects.csv"}


def _night_to_date(n: int) -> str:
    return (PLAN_START + timedelta(days=int(n))).isoformat()


def _date_to_night(s: str) -> int:
    return (date.fromisoformat(s.strip()) - PLAN_START).days


# --------------------------------------------------------------------------- #
# Reading maintenance feeds (TMS / SMMS / TDMS)                                #
# --------------------------------------------------------------------------- #
def _load_defect_feed(path: str) -> tuple[list[Request], dict[str, JobMeta]]:
    """Read one department's defect export into (requests, metadata).

    All three systems share one normalised column set here; in a real deployment
    each adapter would translate that system's own schema into these fields.
    """
    requests: list[Request] = []
    meta: dict[str, JobMeta] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rid = row["defect_id"].strip()
            tier = int(row["tier"])
            crew = _CREW.get(row["department"].strip(), CrewType.PWAY)
            try:
                equipment = Equipment(row["equipment"].strip())
            except ValueError:
                equipment = Equipment.NONE
            requests.append(Request(
                id=rid,
                title=row["description"].strip(),
                section_id=row["section"].strip(),
                duration=hours_to_ticks(float(row["est_duration_h"])),
                priority=_TIER_PRIORITY[tier],
                crew=crew,
                crew_size=int(row.get("crew_size", 1) or 1),
                equipment=equipment,
                earliest_night=_date_to_night(row["detected_date"]),
                latest_night=_date_to_night(row["due_date"]),
            ))
            meta[rid] = JobMeta(
                reason_code=row["reason_code"].strip(),
                department=row["department"].strip(),
                tier=tier,
            )
    return requests, meta


def load_goods_forecast(path: str) -> dict[str, int]:
    """COA goods-trains forecast: section id → freight paths/night."""
    out: dict[str, int] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[row["section"].strip()] = int(float(row["goods_trains_per_night"]))
    return out


def _load_block_availability(path: str) -> list[Window]:
    """COA block availability: which section has an engineering window which night."""
    windows: list[Window] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("available", "yes").strip().lower() in ("no", "false", "0"):
                continue
            windows.append(Window(
                section_id=row["section"].strip(),
                night=_date_to_night(row["date"]),
                start=int(row["window_start"]),
                end=int(row["window_end"]),
            ))
    return windows


# --------------------------------------------------------------------------- #
# Building a scenario purely from feeds                                        #
# --------------------------------------------------------------------------- #
def build_scenario_from_feeds(feeds_dir: str = FEEDS_DIR
                              ) -> tuple[Scenario, dict[str, JobMeta]]:
    """Assemble a planner Scenario from the four upstream feeds on disk."""
    d = Path(feeds_dir)
    corridor = load_corridor()
    goods = load_goods_forecast(str(d / "coa_goods_forecast.csv"))

    sections = [
        Section(id=s.id, name=f"{s.from_name}–{s.to_name}",
                traffic_density=s.trains_per_day + goods.get(s.id, 0))
        for s in corridor
    ]
    windows = _load_block_availability(str(d / "coa_block_availability.csv"))

    requests: list[Request] = []
    meta: dict[str, JobMeta] = {}
    for dept in ("ENGG", "TRD", "SNT"):
        fp = d / _FILE[dept]
        if fp.exists():
            reqs, m = _load_defect_feed(str(fp))
            requests.extend(reqs)
            meta.update(m)

    nights = 1 + max(
        [w.night for w in windows] + [r.latest_night for r in requests] + [0]
    )
    scenario = Scenario(
        sections=sections, windows=windows, requests=requests,
        pool=_gen.resource_pool(), nights=nights, seed=0,
    )
    return scenario, meta


# --------------------------------------------------------------------------- #
# Writing sample feeds from a scenario (stand-in for the live systems)         #
# --------------------------------------------------------------------------- #
def export_feeds(scenario: Scenario, meta: dict[str, JobMeta],
                 goods_forecast: dict[str, int], feeds_dir: str = FEEDS_DIR) -> None:
    """Write the current scenario back out as TMS/SMMS/TDMS/COA export files."""
    d = Path(feeds_dir)
    d.mkdir(parents=True, exist_ok=True)

    # One defect file per source system.
    by_dept: dict[str, list[Request]] = {"ENGG": [], "TRD": [], "SNT": []}
    for r in scenario.requests:
        m = meta.get(r.id)
        if m and m.department in by_dept:
            by_dept[m.department].append(r)

    cols = ["defect_id", "system", "department", "section", "description",
            "reason_code", "tier", "crew_size", "equipment",
            "detected_date", "due_date", "est_duration_h"]
    for dept, reqs in by_dept.items():
        with open(d / _FILE[dept], "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in reqs:
                m = meta[r.id]
                w.writerow({
                    "defect_id": r.id, "system": _SYSTEM[dept], "department": dept,
                    "section": r.section_id, "description": r.title,
                    "reason_code": m.reason_code, "tier": m.tier,
                    "crew_size": r.crew_size, "equipment": r.equipment.value,
                    "detected_date": _night_to_date(r.earliest_night),
                    "due_date": _night_to_date(r.latest_night),
                    "est_duration_h": round(r.duration * 0.5, 1),  # ticks→hours (30-min ticks)
                })

    # COA block availability (which window is open which night).
    with open(d / "coa_block_availability.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "section", "date", "window_start", "window_end", "window_clock", "available"])
        w.writeheader()
        for win in sorted(scenario.windows, key=lambda x: (x.night, x.section_id)):
            w.writerow({
                "section": win.section_id, "date": _night_to_date(win.night),
                "window_start": win.start, "window_end": win.end,
                "window_clock": f"{format_clock(win.start)}-{format_clock(win.end)}",
                "available": "yes",
            })

    # COA goods-trains forecast.
    with open(d / "coa_goods_forecast.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["section", "goods_trains_per_night"])
        w.writeheader()
        for sid, g in goods_forecast.items():
            w.writerow({"section": sid, "goods_trains_per_night": g})


def generate_sample_feeds(seed: int = 3, nights: int = 30, feeds_dir: str = FEEDS_DIR) -> dict:
    """Produce a realistic set of TMS/SMMS/TDMS/COA export files from the synthetic
    generator — a stand-in for pulling today's exports from the live systems."""
    goods = _gen.synth_goods_forecast(seed)
    scenario, meta = _gen.build_scenario(seed=seed, nights=nights, goods_forecast=goods)
    export_feeds(scenario, meta, goods, feeds_dir)
    return {
        "feeds_dir": feeds_dir,
        "defects": len(scenario.requests),
        "windows": len(scenario.windows),
        "goods_sections": len(goods),
    }
